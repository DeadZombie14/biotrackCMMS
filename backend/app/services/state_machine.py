import hashlib
import secrets
from datetime import date, datetime, timedelta, timezone
from app.extensions import db
from app.models import Certification, DispatchAlert, IncidentReport, MedicalAsset, User, WorkOrder
from app.services.audit_service import record_audit_event
from app.services.dispatch_service import create_critical_dispatch_alert, sse_broker
from app.services.folio_service import generate_unique_folio


class StateTransitionError(Exception):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# Strict server-side allowed transitions (SDS Section 6, Figure 2)
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "OPERATIVO": {"REPORTADO", "BLOQUEADO", "EN_MANTENIMIENTO_PREVENTIVO"},
    "REPORTADO": {"EN_DIAGNOSTICO"},
    "BLOQUEADO": {"EN_DIAGNOSTICO"},
    "EN_MANTENIMIENTO_PREVENTIVO": {"EN_DIAGNOSTICO", "EN_CALIBRACION"},
    "EN_DIAGNOSTICO": {"EN_ESPERA_REFACCION", "EN_CALIBRACION", "BAJA_DEFINITIVA"},
    "EN_ESPERA_REFACCION": {"EN_DIAGNOSTICO"},
    "EN_CALIBRACION": {"CERTIFICADO_PENDIENTE_RECEPCION"},
    "CERTIFICADO_PENDIENTE_RECEPCION": {"OPERATIVO", "EN_DIAGNOSTICO"},
    "BAJA_DEFINITIVA": set(),
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _assert_transition(asset: MedicalAsset, target_state: str):
    allowed = ALLOWED_TRANSITIONS.get(asset.current_state, set())
    if target_state not in allowed:
        raise StateTransitionError(
            f"Transición no permitida: {asset.current_state} → {target_state}. "
            f"Regla de máquina de estados en servidor (AD-03).",
            status_code=409,
        )


def _sign_hash(user: User, context: str, timestamp: datetime) -> str:
    raw = f"{user.id}|{user.directory_uid}|{user.role}|{context}|{timestamp.isoformat()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def report_incident_atomic(
    *,
    asset: MedicalAsset,
    actor: User,
    severity: str,
    symptom_text: str,
    symptom_id: int | None = None,
    notes: str | None = None,
    terminal_ip: str | None = None,
    is_deferred: bool = False,
    declared_occurred_at: datetime | None = None,
    escalation_timeout_override: int | None = None,
) -> tuple[IncidentReport, WorkOrder, DispatchAlert | None]:
    """
    Atomic ACID reporting flow (QA-01, QA-02, SDS Section 7):
    - CRITICA triggers Fail-Safe: OPERATIVO -> BLOQUEADO (< 2s) + On-Call Dispatch.
    - MEDIA / BAJA transitions OPERATIVO -> REPORTADO.
    """
    severity = severity.upper()
    if severity not in ("CRITICA", "MEDIA", "BAJA"):
        raise StateTransitionError("Severidad inválida. Use CRITICA, MEDIA o BAJA.", 400)

    is_failsafe = severity == "CRITICA"
    target_state = "BLOQUEADO" if is_failsafe else "REPORTADO"
    _assert_transition(asset, target_state)

    try:
        incident = IncidentReport(
            hospital_id=asset.hospital_id,
            asset_id=asset.id,
            event_type="FALLA_CORRECTIVA",
            severity=severity,
            symptom_id=symptom_id,
            symptom_text=symptom_text,
            notes=notes,
            reported_by_id=actor.id,
            terminal_ip=terminal_ip,
            is_deferred=is_deferred,
            declared_occurred_at=declared_occurred_at,
        )
        db.session.add(incident)
        db.session.flush()

        previous_state = asset.current_state
        asset.current_state = target_state
        if is_failsafe:
            asset.has_critical_flag = True

        wo = WorkOrder(
            hospital_id=asset.hospital_id,
            incident_report_id=incident.id,
            asset_id=asset.id,
            service_type="CORRECTIVO",
            status="ABIERTA",
        )
        db.session.add(wo)
        db.session.flush()

        record_audit_event(
            hospital_id=asset.hospital_id,
            asset_id=asset.id,
            event_type="INCIDENT_REPORTED",
            actor_user_id=actor.id,
            payload={
                "incident_id": incident.id,
                "work_order_id": wo.id,
                "severity": severity,
                "symptom": symptom_text,
                "previous_state": previous_state,
                "new_state": target_state,
                "is_deferred": is_deferred,
                "declared_occurred_at": declared_occurred_at.isoformat() if declared_occurred_at else None,
            },
        )

        alert = None
        if is_failsafe:
            record_audit_event(
                hospital_id=asset.hospital_id,
                asset_id=asset.id,
                event_type="ASSET_BLOCKED_FAILSAFE",
                actor_user_id=actor.id,
                payload={
                    "incident_id": incident.id,
                    "inventory_code": asset.inventory_code,
                    "risk_class": asset.risk_class,
                    "message": "Equipo bloqueado por seguridad, retirar de atención a pacientes.",
                },
            )
            alert = create_critical_dispatch_alert(
                asset=asset,
                incident_report_id=incident.id,
                symptom_text=symptom_text,
                actor_user_id=actor.id,
                timeout_seconds=escalation_timeout_override,
            )

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    # Publish real-time SSE events after ACID COMMIT
    if is_failsafe and alert:
        sse_broker.publish("critical_block", alert.to_dict())
    else:
        sse_broker.publish(
            "incident_reported",
            {
                "asset_id": asset.id,
                "inventory_code": asset.inventory_code,
                "severity": severity,
                "state": asset.current_state,
            },
        )

    return incident, wo, alert


def start_preventive_maintenance(asset: MedicalAsset, actor: User, notes: str | None = None) -> WorkOrder:
    """Scenario 5: Transition OPERATIVO -> EN_MANTENIMIENTO_PREVENTIVO."""
    _assert_transition(asset, "EN_MANTENIMIENTO_PREVENTIVO")
    try:
        incident = IncidentReport(
            hospital_id=asset.hospital_id,
            asset_id=asset.id,
            event_type="PREVENTIVO_PROGRAMADO",
            severity="BAJA",
            symptom_text="Mantenimiento preventivo programado conforme a calendario del fabricante",
            notes=notes,
            reported_by_id=actor.id,
        )
        db.session.add(incident)
        db.session.flush()

        asset.current_state = "EN_MANTENIMIENTO_PREVENTIVO"
        wo = WorkOrder(
            hospital_id=asset.hospital_id,
            incident_report_id=incident.id,
            asset_id=asset.id,
            biomedical_user_id=actor.id,
            service_type="PREVENTIVO",
            status="EN_DIAGNOSTICO",
        )
        db.session.add(wo)
        db.session.flush()

        record_audit_event(
            hospital_id=asset.hospital_id,
            asset_id=asset.id,
            event_type="PREVENTIVE_STARTED",
            actor_user_id=actor.id,
            payload={"work_order_id": wo.id, "notes": notes},
        )
        db.session.commit()
        return wo
    except Exception:
        db.session.rollback()
        raise


def record_periodic_inspection(
    asset: MedicalAsset, actor: User, result_notes: str
) -> Certification:
    """AD-09: Periodic inspection on an OPERATIVO asset renews validity without panic alarms."""
    if asset.current_state != "OPERATIVO":
        raise StateTransitionError(
            "La inspección periódica solo aplica a equipos en estado OPERATIVO.", 409
        )
    try:
        now = _utcnow()
        today = date.today()
        next_due = today + timedelta(days=asset.preventive_interval_days)

        incident = IncidentReport(
            hospital_id=asset.hospital_id,
            asset_id=asset.id,
            event_type="INSPECCION_PERIODICA",
            severity="BAJA",
            symptom_text="Inspección periódica de funcionamiento y seguridad eléctrica",
            notes=result_notes,
            reported_by_id=actor.id,
        )
        db.session.add(incident)
        db.session.flush()

        wo = WorkOrder(
            hospital_id=asset.hospital_id,
            incident_report_id=incident.id,
            asset_id=asset.id,
            biomedical_user_id=actor.id,
            service_type="INSPECCION",
            technical_diagnosis=result_notes,
            status="CERRADA",
            closed_at=now,
        )
        db.session.add(wo)
        db.session.flush()

        folio = generate_unique_folio(today.year)
        sig_hash = _sign_hash(actor, f"INSPECTION|{folio}|{asset.serial_number}", now)
        cert = Certification(
            hospital_id=asset.hospital_id,
            work_order_id=wo.id,
            asset_id=asset.id,
            folio_biotrack=folio,
            metrological_result=result_notes,
            service_date=today,
            expiration_date=next_due,
            biomedical_signer_id=actor.id,
            biomedical_signed_at=now,
            biomedical_signature_hash=sig_hash,
            area_receiver_id=actor.id,
            area_received_at=now,
            area_signature_hash=sig_hash,
            public_qr_token=secrets.token_urlsafe(18),
        )
        db.session.add(cert)
        asset.last_service_date = today
        asset.next_preventive_date = next_due
        db.session.flush()

        record_audit_event(
            hospital_id=asset.hospital_id,
            asset_id=asset.id,
            event_type="PERIODIC_INSPECTION_COMPLETED",
            actor_user_id=actor.id,
            payload={
                "folio_biotrack": folio,
                "result": result_notes,
                "next_preventive_date": next_due.isoformat(),
            },
        )
        db.session.commit()
        return cert
    except Exception:
        db.session.rollback()
        raise


def take_work_order(wo: WorkOrder, actor: User) -> WorkOrder:
    """Reportado / Bloqueado / Preventivo -> En diagnóstico."""
    asset = wo.asset
    _assert_transition(asset, "EN_DIAGNOSTICO")
    try:
        prev = asset.current_state
        asset.current_state = "EN_DIAGNOSTICO"
        wo.biomedical_user_id = actor.id
        wo.status = "EN_DIAGNOSTICO"

        # Auto-acknowledge pending dispatch alerts for this incident
        pending_alerts = DispatchAlert.query.filter_by(
            incident_report_id=wo.incident_report_id, status="PENDIENTE"
        ).all()
        now = _utcnow()
        for al in pending_alerts:
            al.status = "ACUSADO"
            al.acknowledged_at = now

        record_audit_event(
            hospital_id=asset.hospital_id,
            asset_id=asset.id,
            event_type="WORK_ORDER_TAKEN",
            actor_user_id=actor.id,
            payload={
                "work_order_id": wo.id,
                "previous_state": prev,
                "new_state": "EN_DIAGNOSTICO",
                "has_critical_flag": asset.has_critical_flag,
            },
        )
        db.session.commit()
        return wo
    except Exception:
        db.session.rollback()
        raise


def transition_work_order_diagnosis(
    wo: WorkOrder,
    actor: User,
    *,
    technical_diagnosis: str | None = None,
    parts_used: str | None = None,
    parts_cost: float | None = None,
    target_state: str | None = None,
) -> WorkOrder:
    """Update diagnosis/parts and optionally transition to EN_ESPERA_REFACCION, EN_DIAGNOSTICO, EN_CALIBRACION, or BAJA_DEFINITIVA."""
    asset = wo.asset
    if target_state == "BAJA_DEFINITIVA" and actor.role != "JEFE_TALLER":
        raise StateTransitionError(
            "Solo el Jefe de Taller Biomédico puede dictaminar Baja Definitiva.", 403
        )
    if target_state:
        _assert_transition(asset, target_state)

    try:
        if technical_diagnosis is not None:
            wo.technical_diagnosis = technical_diagnosis
        if parts_used is not None:
            wo.parts_used = parts_used
        if parts_cost is not None:
            wo.parts_cost = parts_cost

        prev = asset.current_state
        if target_state:
            asset.current_state = target_state
            status_map = {
                "EN_DIAGNOSTICO": "EN_DIAGNOSTICO",
                "EN_ESPERA_REFACCION": "ESPERA_REFACCION",
                "EN_CALIBRACION": "EN_CALIBRACION",
                "BAJA_DEFINITIVA": "BAJA_DEFINITIVA",
            }
            wo.status = status_map.get(target_state, wo.status)
            if target_state == "BAJA_DEFINITIVA":
                wo.closed_at = _utcnow()

        record_audit_event(
            hospital_id=asset.hospital_id,
            asset_id=asset.id,
            event_type=f"WORK_ORDER_{target_state or 'UPDATED'}",
            actor_user_id=actor.id,
            payload={
                "work_order_id": wo.id,
                "previous_state": prev,
                "new_state": asset.current_state,
                "diagnosis": wo.technical_diagnosis,
                "parts_used": wo.parts_used,
                "parts_cost": float(wo.parts_cost or 0),
            },
        )
        db.session.commit()
        return wo
    except Exception:
        db.session.rollback()
        raise


def certify_work_order_firma1(
    wo: WorkOrder,
    actor: User,
    *,
    metrological_result: str,
    external_lab_folio: str | None = None,
    external_cert_note: str | None = None,
) -> Certification:
    """
    Two-Person Rule — Firma 1 (Biomedical Engineer with password re-auth):
    EN_CALIBRACION -> CERTIFICADO_PENDIENTE_RECEPCION + Unique Folio CAL-YYYY-XXXXX.
    """
    asset = wo.asset
    _assert_transition(asset, "CERTIFICADO_PENDIENTE_RECEPCION")

    try:
        now = _utcnow()
        today = date.today()
        expiration = today + timedelta(days=asset.preventive_interval_days)
        folio = generate_unique_folio(today.year)
        sig_hash = _sign_hash(actor, f"FIRMA1|{folio}|{asset.serial_number}", now)

        cert = Certification(
            hospital_id=asset.hospital_id,
            work_order_id=wo.id,
            asset_id=asset.id,
            folio_biotrack=folio,
            external_lab_folio=external_lab_folio,
            external_cert_note=external_cert_note,
            metrological_result=metrological_result,
            service_date=today,
            expiration_date=expiration,
            biomedical_signer_id=actor.id,
            biomedical_signed_at=now,
            biomedical_signature_hash=sig_hash,
            public_qr_token=secrets.token_urlsafe(18),
        )
        db.session.add(cert)

        asset.current_state = "CERTIFICADO_PENDIENTE_RECEPCION"
        wo.status = "CERTIFICADA"
        db.session.flush()

        record_audit_event(
            hospital_id=asset.hospital_id,
            asset_id=asset.id,
            event_type="CERTIFICATION_FIRMA1_BIOMEDICAL",
            actor_user_id=actor.id,
            payload={
                "work_order_id": wo.id,
                "folio_biotrack": folio,
                "external_lab_folio": external_lab_folio,
                "metrological_result": metrological_result,
                "biomedical_signature_hash": sig_hash,
                "new_state": "CERTIFICADO_PENDIENTE_RECEPCION",
            },
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    sse_broker.publish(
        "pending_reception",
        {
            "work_order_id": wo.id,
            "asset_id": asset.id,
            "inventory_code": asset.inventory_code,
            "folio_biotrack": cert.folio_biotrack,
            "area_id": asset.area_id,
        },
    )
    return cert


def confirm_reception_firma2(wo: WorkOrder, actor: User, reception_notes: str | None = None) -> Certification:
    """
    Two-Person Rule — Firma 2 (Area Responsible with password re-auth):
    CERTIFICADO_PENDIENTE_RECEPCION -> OPERATIVO + QR Sticker activation.
    """
    asset = wo.asset
    if actor.role != "RESPONSABLE_AREA":
        raise StateTransitionError(
            "Solo el Responsable del Área Clínica puede ejecutar la Firma 2 de recepción (QA-06).",
            403,
        )
    if not wo.certification:
        raise StateTransitionError("No existe certificación técnica (Firma 1) previa.", 409)
    if wo.certification.biomedical_signer_id == actor.id:
        raise StateTransitionError(
            "Regla de Doble Autorización (Two-Person Rule): el firmante de recepción debe ser distinto al biomédico certificador.",
            403,
        )

    _assert_transition(asset, "OPERATIVO")

    try:
        now = _utcnow()
        cert = wo.certification
        sig_hash = _sign_hash(actor, f"FIRMA2|{cert.folio_biotrack}|{asset.serial_number}", now)

        cert.area_receiver_id = actor.id
        cert.area_received_at = now
        cert.area_signature_hash = sig_hash

        asset.current_state = "OPERATIVO"
        asset.has_critical_flag = False
        asset.last_service_date = cert.service_date
        asset.next_preventive_date = cert.expiration_date

        wo.status = "CERRADA"
        wo.closed_at = now

        # Mark any related dispatch alerts as RESUELTO
        alerts = DispatchAlert.query.filter_by(incident_report_id=wo.incident_report_id).all()
        for al in alerts:
            al.status = "RESUELTO"

        record_audit_event(
            hospital_id=asset.hospital_id,
            asset_id=asset.id,
            event_type="RECEPTION_FIRMA2_AREA_OPERATIVE",
            actor_user_id=actor.id,
            payload={
                "work_order_id": wo.id,
                "folio_biotrack": cert.folio_biotrack,
                "area_signature_hash": sig_hash,
                "public_qr_token": cert.public_qr_token,
                "reception_notes": reception_notes,
                "new_state": "OPERATIVO",
            },
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    sse_broker.publish(
        "asset_operative",
        {
            "asset_id": asset.id,
            "inventory_code": asset.inventory_code,
            "folio_biotrack": cert.folio_biotrack,
        },
    )
    return cert


def dismiss_false_positive(wo: WorkOrder, actor: User, reason: str) -> WorkOrder:
    """
    Allow Biomedical Engineer / On-Call to dismiss a false positive without penalizing
    availability, MTTR, or SLA metrics. Logs immutable audit event for transparency.
    """
    asset = wo.asset
    if asset.current_state not in ("REPORTADO", "BLOQUEADO", "EN_DIAGNOSTICO", "EN_CALIBRACION"):
        raise StateTransitionError(
            f"No se puede marcar como falso positivo en estado {asset.current_state}.", 409
        )
    if wo.service_type != "CORRECTIVO":
        raise StateTransitionError(
            "Solo las órdenes por falla correctiva pueden desestimarse como falso positivo.", 409
        )

    try:
        now = _utcnow()
        prev_state = asset.current_state
        asset.current_state = "OPERATIVO"
        asset.has_critical_flag = False

        wo.biomedical_user_id = wo.biomedical_user_id or actor.id
        wo.status = "FALSO_POSITIVO"
        wo.technical_diagnosis = f"[FALSO POSITIVO DESESTIMADO]: {reason}"
        wo.parts_cost = 0
        wo.closed_at = now

        alerts = DispatchAlert.query.filter_by(incident_report_id=wo.incident_report_id).all()
        for al in alerts:
            al.status = "RESUELTO"
            if not al.acknowledged_at:
                al.acknowledged_at = now

        record_audit_event(
            hospital_id=asset.hospital_id,
            asset_id=asset.id,
            event_type="WORK_ORDER_DISMISSED_FALSE_POSITIVE",
            actor_user_id=actor.id,
            payload={
                "work_order_id": wo.id,
                "previous_state": prev_state,
                "new_state": "OPERATIVO",
                "reason": reason,
                "sla_impact": "Excluido de métricas de falla, MTTR y disponibilidad",
            },
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    sse_broker.publish(
        "asset_operative",
        {
            "asset_id": asset.id,
            "inventory_code": asset.inventory_code,
            "dismissed_false_positive": True,
        },
    )
    return wo


def reject_reception_firma2(wo: WorkOrder, actor: User, rejection_reason: str) -> WorkOrder:
    """
    Allow Area Responsible (Firma 2) to reject a certified handoff and return the asset
    to Biomedical Workshop (EN_DIAGNOSTICO) for further review.
    """
    asset = wo.asset
    if actor.role != "RESPONSABLE_AREA":
        raise StateTransitionError(
            "Solo el Responsable del Área Clínica puede rechazar la recepción (Firma 2).", 403
        )
    _assert_transition(asset, "EN_DIAGNOSTICO")

    try:
        prev_folio = wo.certification.folio_biotrack if wo.certification else None
        if wo.certification:
            db.session.delete(wo.certification)

        asset.current_state = "EN_DIAGNOSTICO"
        wo.status = "EN_DIAGNOSTICO"
        prefix = f"[RECHAZADO EN RECEPCIÓN por {actor.full_name}]: {rejection_reason}"
        wo.technical_diagnosis = (
            f"{prefix}\n---\n{wo.technical_diagnosis}" if wo.technical_diagnosis else prefix
        )

        record_audit_event(
            hospital_id=asset.hospital_id,
            asset_id=asset.id,
            event_type="RECEPTION_REJECTED_BY_AREA",
            actor_user_id=actor.id,
            payload={
                "work_order_id": wo.id,
                "rejected_folio": prev_folio,
                "rejection_reason": rejection_reason,
                "new_state": "EN_DIAGNOSTICO",
            },
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    sse_broker.publish(
        "reception_rejected",
        {
            "work_order_id": wo.id,
            "asset_id": asset.id,
            "inventory_code": asset.inventory_code,
            "rejection_reason": rejection_reason,
        },
    )
    return wo
