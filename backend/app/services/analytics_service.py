from collections import defaultdict
from datetime import date, timedelta
from app.models import ClinicalArea, IncidentReport, MedicalAsset, WorkOrder


def compute_executive_kpis(hospital_id: int) -> dict:
    """
    Calculate the 5 Executive KPIs defined in ConOps v0.2 Section 4.4:
    1. Availability by clinical area and by asset.
    2. Mean Time to Re-entry (MTTR) from report to operational return (hours).
    3. Assets with highest failure recurrence.
    4. Preventive maintenance compliance (completed, due soon <= 15 days, overdue).
    5. Cumulative spare parts cost vs replacement cost per asset.
    """
    areas = ClinicalArea.query.filter_by(hospital_id=hospital_id).all()
    assets = MedicalAsset.query.filter_by(hospital_id=hospital_id).all()
    incidents = IncidentReport.query.filter_by(hospital_id=hospital_id).all()
    work_orders = WorkOrder.query.filter_by(hospital_id=hospital_id).all()

    active_assets = [a for a in assets if a.current_state != "BAJA_DEFINITIVA"]
    operative_count = sum(1 for a in active_assets if a.current_state == "OPERATIVO")
    blocked_count = sum(1 for a in active_assets if a.current_state == "BLOQUEADO")
    overall_availability = (
        round((operative_count / len(active_assets)) * 100, 1) if active_assets else 100.0
    )

    # 1. Availability by clinical area
    availability_by_area = []
    for area in areas:
        area_assets = [a for a in active_assets if a.area_id == area.id]
        op = sum(1 for a in area_assets if a.current_state == "OPERATIVO")
        blk = sum(1 for a in area_assets if a.current_state == "BLOQUEADO")
        pct = round((op / len(area_assets)) * 100, 1) if area_assets else 100.0
        availability_by_area.append(
            {
                "area_id": area.id,
                "area_name": area.name,
                "criticality_level": area.criticality_level,
                "total_assets": len(area_assets),
                "operative_assets": op,
                "blocked_assets": blk,
                "availability_pct": pct,
            }
        )

    # Identify false-positive incident IDs so they NEVER penalize SLA, MTTR, or failure counts
    false_positive_incident_ids = {
        wo.incident_report_id for wo in work_orders if wo.status == "FALSO_POSITIVO"
    }

    # 2. MTTR (hours from incident report creation to work order closure, excluding false positives)
    repair_hours = []
    downtime_by_asset: dict[int, float] = defaultdict(float)
    for wo in work_orders:
        if (
            wo.service_type == "CORRECTIVO"
            and wo.status == "CERRADA"
            and wo.closed_at
            and wo.incident
            and wo.incident.created_at
        ):
            delta_h = max((wo.closed_at - wo.incident.created_at).total_seconds() / 3600.0, 0.25)
            repair_hours.append(delta_h)
            downtime_by_asset[wo.asset_id] += delta_h
    mttr_hours = round(sum(repair_hours) / len(repair_hours), 1) if repair_hours else 0.0

    # 3. Recurring failures per asset (excluding dismissed false positives)
    failure_counts: dict[int, int] = defaultdict(int)
    for inc in incidents:
        if inc.event_type == "FALLA_CORRECTIVA" and inc.id not in false_positive_incident_ids:
            failure_counts[inc.asset_id] += 1

    # 5. Cumulative parts cost vs replacement cost (excluding false positives)
    parts_cost_by_asset: dict[int, float] = defaultdict(float)
    for wo in work_orders:
        if wo.status != "FALSO_POSITIVO":
            parts_cost_by_asset[wo.asset_id] += float(wo.parts_cost or 0)

    asset_metrics = []
    for asset in assets:
        f_count = failure_counts.get(asset.id, 0)
        p_cost = round(parts_cost_by_asset.get(asset.id, 0.0), 2)
        r_cost = float(asset.replacement_cost or 1)
        cost_ratio_pct = round((p_cost / r_cost) * 100, 1) if r_cost > 0 else 0.0
        down_h = round(downtime_by_asset.get(asset.id, 0.0), 1)
        # Annualized downtime % (based on 8760h/year)
        downtime_pct = round(min((down_h / 8760.0) * 100, 100.0), 1)

        if cost_ratio_pct >= 60 or downtime_pct >= 35 or f_count >= 5:
            recommendation = "REEMPLAZO_URGENTE"
        elif cost_ratio_pct >= 35 or f_count >= 3:
            recommendation = "EVALUAR_SUSTITUCION"
        else:
            recommendation = "CONTINUIDAD_OPERATIVA"

        asset_metrics.append(
            {
                "asset_id": asset.id,
                "inventory_code": asset.inventory_code,
                "serial_number": asset.serial_number,
                "device_type": asset.device_type,
                "brand": asset.brand,
                "model": asset.model,
                "area_name": asset.area.name if asset.area else None,
                "current_state": asset.current_state,
                "failure_count": f_count,
                "downtime_hours": down_h,
                "downtime_pct": downtime_pct,
                "cumulative_parts_cost": p_cost,
                "replacement_cost": r_cost,
                "cost_ratio_pct": cost_ratio_pct,
                "recommendation": recommendation,
            }
        )

    top_recurring_failures = sorted(
        asset_metrics, key=lambda x: (x["failure_count"], x["downtime_hours"]), reverse=True
    )[:8]

    cost_vs_replacement = sorted(
        asset_metrics, key=lambda x: x["cost_ratio_pct"], reverse=True
    )

    # 4. Preventive maintenance compliance
    today = date.today()
    due_soon_limit = today + timedelta(days=15)
    prev_on_time = 0
    prev_due_soon = 0
    prev_overdue = 0
    for asset in active_assets:
        if not asset.next_preventive_date:
            prev_overdue += 1
        elif asset.next_preventive_date < today:
            prev_overdue += 1
        elif asset.next_preventive_date <= due_soon_limit:
            prev_due_soon += 1
        else:
            prev_on_time += 1

    prev_completed_total = sum(
        1 for wo in work_orders if wo.service_type == "PREVENTIVO" and wo.status == "CERRADA"
    )
    compliance_pct = (
        round(((prev_on_time + prev_due_soon) / len(active_assets)) * 100, 1)
        if active_assets
        else 100.0
    )

    return {
        "summary": {
            "total_active_assets": len(active_assets),
            "operative_assets": operative_count,
            "blocked_assets": blocked_count,
            "overall_availability_pct": overall_availability,
            "mttr_hours": mttr_hours,
            "preventive_compliance_pct": compliance_pct,
            "replacement_candidates_count": sum(
                1 for m in asset_metrics if m["recommendation"] == "REEMPLAZO_URGENTE"
            ),
            "false_positives_dismissed": len(false_positive_incident_ids),
        },
        "availability_by_area": availability_by_area,
        "top_recurring_failures": top_recurring_failures,
        "preventive_compliance": {
            "on_time": prev_on_time,
            "due_soon_15d": prev_due_soon,
            "overdue": prev_overdue,
            "completed_historical": prev_completed_total,
            "compliance_pct": compliance_pct,
        },
        "cost_vs_replacement": cost_vs_replacement,
    }
