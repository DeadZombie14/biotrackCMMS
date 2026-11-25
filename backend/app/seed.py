import hashlib
import secrets
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import text
from app.extensions import db
from app.models import (
    AuditEvent,
    Certification,
    ClinicalArea,
    DispatchAlert,
    Hospital,
    IncidentReport,
    MedicalAsset,
    OnCallRoster,
    SymptomCatalog,
    User,
    WorkOrder,
)
from app.services.audit_service import (
    install_mariadb_immutability_triggers,
    record_audit_event,
)
from app.services.folio_service import generate_unique_folio


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _sig_hash(user: User, context: str, dt: datetime) -> str:
    return hashlib.sha256(
        f"{user.id}|{user.directory_uid}|{user.role}|{context}|{dt.isoformat()}".encode("utf-8")
    ).hexdigest()


def run_seed(reset: bool = False):
    if reset:
        # Temporarily drop audit immutability triggers so --reset works cleanly in dev
        db.session.execute(text("DROP TRIGGER IF EXISTS trg_audit_events_no_update"))
        db.session.execute(text("DROP TRIGGER IF EXISTS trg_audit_events_no_delete"))
        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in [
            "dispatch_alerts",
            "audit_events",
            "certifications",
            "work_orders",
            "incident_reports",
            "on_call_rosters",
            "symptom_catalog",
            "medical_assets",
            "users",
            "clinical_areas",
            "hospitals",
        ]:
            db.session.execute(text(f"TRUNCATE TABLE {table}"))
        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        db.session.commit()

    if Hospital.query.filter_by(code="HBT-01").first():
        install_mariadb_immutability_triggers()
        return

    # 1. Hospital (Tenant)
    hospital = Hospital(
        name="Hospital BioTrack",
        code="HBT-01",
        municipality="Zona Metropolitana",
        address="Av. Salud 100, Centro Médico",
        unit_type="Hospital de Especialidades",
    )
    db.session.add(hospital)
    db.session.flush()

    # 2. Clinical Areas
    areas_data = [
        ("Unidad de Cuidados Intensivos (UCI)", "UCI-01", "CRITICA", "TERM-UCI-01"),
        ("Urgencias Adultos", "URG-01", "ALTA", "TERM-URG-01"),
        ("Quirófano Central", "QRF-01", "CRITICA", "TERM-QRF-01"),
        ("Laboratorio Clínico", "LAB-01", "MEDIA", "TERM-LAB-01"),
    ]
    areas = {}
    for name, code, crit, term in areas_data:
        area = ClinicalArea(
            hospital_id=hospital.id,
            name=name,
            area_code=code,
            criticality_level=crit,
            terminal_identifier=term,
        )
        db.session.add(area)
        db.session.flush()
        areas[code] = area

    # 3. Institutional Users (all 6 roles, demo password: BioTrack2026!)
    users_data = [
        ("clinico.uci", "Dra. Sofía Mendoza (Clínico UCI)", "clinico@biotrack.mx", "33-3614-1001", "CLINICO", areas["UCI-01"].id),
        ("biomedico.guardia", "Ing. Luis Armando Dueñas (Biomédico)", "biomedico@biotrack.mx", "33-3614-2001", "BIOMEDICO", None),
        ("jefe.taller", "Ing. Oscar David Flores (Jefe de Taller)", "jefe.taller@biotrack.mx", "33-3614-2000", "JEFE_TALLER", None),
        ("resp.uci", "Enf. Araceli Moreno (Resp. Área UCI)", "responsable@biotrack.mx", "33-3614-3001", "RESPONSABLE_AREA", areas["UCI-01"].id),
        ("direccion.medica", "Lic. Dalia Edith Ponce (Dirección)", "direccion@biotrack.mx", "33-3614-4001", "DIRECCION", None),
        ("auditor.cofepris", "Mtro. Carlos Guzmán (Auditor COFEPRIS)", "auditor@cofepris.mx", "33-3614-5001", "AUDITOR", None),
    ]
    users = {}
    for uid, full_name, email, phone, role, area_id in users_data:
        u = User(
            hospital_id=hospital.id,
            area_id=area_id,
            directory_uid=uid,
            full_name=full_name,
            email=email,
            phone=phone,
            role=role,
            is_active=True,
        )
        u.set_password("BioTrack2026!")
        db.session.add(u)
        db.session.flush()
        users[role] = u

    # 4. Active On-Call Roster (covering 24/7 for demo)
    now = _utcnow()
    roster = OnCallRoster(
        hospital_id=hospital.id,
        biomedical_user_id=users["BIOMEDICO"].id,
        coverage_areas_json=[a.id for a in areas.values()],
        start_time=now - timedelta(hours=12),
        end_time=now + timedelta(days=30),
        contact_phone=users["BIOMEDICO"].phone,
        is_active=True,
    )
    db.session.add(roster)

    # 5. Closed Symptom Catalog (QA-02: Zero free-text required)
    symptoms_seed = [
        ("Bomba de Infusión Volumétrica", "Detención súbita sin causa mecánica aparente", "CRITICA", "Mecánica"),
        ("Bomba de Infusión Volumétrica", "Desviación en tasa de infusión (flujo mL/h inexacto)", "CRITICA", "Calibración"),
        ("Bomba de Infusión Volumétrica", "Falsa alarma constante de oclusión de línea", "MEDIA", "Sensor"),
        ("Monitor de Signos Vitales", "Lecturas inconsistentes de presión arterial no invasiva (NIBP)", "MEDIA", "Sensor"),
        ("Monitor de Signos Vitales", "Pérdida intermitente de señal de ECG / SpO2", "CRITICA", "Eléctrica"),
        ("Monitor de Signos Vitales", "Batería interna no retiene carga en traslado", "BAJA", "Alimentación"),
        ("Ventilador Mecánico UCI", "Alarma de presión inspiratoria máxima no responde", "CRITICA", "Sensor"),
        ("Ventilador Mecánico UCI", "Fuga en celda de oxígeno (FiO2 inestable)", "CRITICA", "Neumática"),
        ("Ventilador Mecánico UCI", "Fallo en pantalla táctil de configuración", "MEDIA", "Interfaz"),
        ("Desfibrilador Bifásico", "Falla en autotest de descarga de energía (30J/200J)", "CRITICA", "Eléctrica"),
        ("Desfibrilador Bifásico", "Error de impedancia en paletas de desfibrilación", "CRITICA", "Hardware"),
        ("Máquina de Anestesia", "Fuga en circuito respiratorio / vaporizador inestable", "CRITICA", "Neumática"),
        ("Máquina de Anestesia", "Falla en sensor de flujo espiratorio", "MEDIA", "Sensor"),
        ("Centrífuga de Laboratorio", "Rotor bloqueado / falla de giro", "MEDIA", "Mecánica"),
        ("Analizador de Gases en Sangre", "Desviación en calibración de pH y gases arteriales", "MEDIA", "Calibración"),
    ]
    for dev_type, desc, sev, cat in symptoms_seed:
        db.session.add(
            SymptomCatalog(
                device_type=dev_type,
                description=desc,
                default_severity=sev,
                category=cat,
            )
        )

    # 6. Medical Assets (designed to showcase ALL 5 ConOps v0.2 scenarios)
    today = date.today()
    assets_seed = [
        # Scenario 2 ready: UCI Infusion Pumps
        ("UCI-BOM-01", "BAX-CXE-2023-001", "Baxter", "Colleague CXE", "Bomba de Infusión Volumétrica", "UCI-01", "SOPORTE_VIDA", 4200, 180, today - timedelta(days=45), today + timedelta(days=135)),
        ("UCI-BOM-02", "BAX-CXE-2023-002", "Baxter", "Colleague CXE", "Bomba de Infusión Volumétrica", "UCI-01", "SOPORTE_VIDA", 4200, 180, today - timedelta(days=60), today + timedelta(days=120)),
        # Scenario 5 ready: 3 ICU Ventilators due for preventive maintenance in 10 days!
        ("UCI-VEN-01", "HAM-C6-2022-101", "Hamilton Medical", "Hamilton-C6", "Ventilador Mecánico UCI", "UCI-01", "SOPORTE_VIDA", 35000, 180, today - timedelta(days=170), today + timedelta(days=10)),
        ("UCI-VEN-02", "HAM-C6-2022-102", "Hamilton Medical", "Hamilton-C6", "Ventilador Mecánico UCI", "UCI-01", "SOPORTE_VIDA", 35000, 180, today - timedelta(days=170), today + timedelta(days=10)),
        ("UCI-VEN-03", "HAM-C6-2022-103", "Hamilton Medical", "Hamilton-C6", "Ventilador Mecánico UCI", "UCI-01", "SOPORTE_VIDA", 35000, 180, today - timedelta(days=172), today + timedelta(days=8)),
        # Scenario 1 ready: Urgencias Monitors
        ("URG-MON-04", "MIN-N17-2023-004", "Mindray", "BeneVision N17", "Monitor de Signos Vitales", "URG-01", "SOPORTE_VIDA", 12000, 180, today - timedelta(days=30), today + timedelta(days=150)),
        ("URG-MON-05", "MIN-N17-2023-005", "Mindray", "BeneVision N17", "Monitor de Signos Vitales", "URG-01", "SOPORTE_VIDA", 12000, 180, today - timedelta(days=90), today + timedelta(days=90)),
        # Scenario 3 ready: Defibrillator with verified calibration 7 days ago
        ("URG-DES-01", "ZOL-RSP-2022-001", "Zoll", "R Series Plus", "Desfibrilador Bifásico", "URG-01", "SOPORTE_VIDA", 16500, 180, today - timedelta(days=7), today + timedelta(days=173)),
        # Scenario 4 ready: Aging Anesthesia Machines in Quirófano with high downtime & parts cost > replacement
        ("QRF-ANE-01", "DRG-FAB-2018-001", "Dräger", "Fabius Plus XL", "Máquina de Anestesia", "QRF-01", "SOPORTE_VIDA", 28000, 180, today - timedelta(days=190), today - timedelta(days=10)),
        ("QRF-ANE-02", "DRG-FAB-2018-002", "Dräger", "Fabius Plus XL", "Máquina de Anestesia", "QRF-01", "SOPORTE_VIDA", 28000, 180, today - timedelta(days=185), today - timedelta(days=5)),
        # Lab assets
        ("LAB-CEN-01", "EPP-5810R-2021-01", "Eppendorf", "5810R", "Centrífuga de Laboratorio", "LAB-01", "NO_CRITICO", 8500, 180, today - timedelta(days=40), today + timedelta(days=140)),
        ("LAB-GAS-01", "RAD-ABL800-2022-01", "Radiometer", "ABL800 Flex", "Analizador de Gases en Sangre", "LAB-01", "NO_CRITICO", 26000, 180, today - timedelta(days=25), today + timedelta(days=155)),
    ]

    created_assets = {}
    for inv, serial, brand, model, dtype, area_code, risk, cost, interval, last_svc, next_prev in assets_seed:
        asset = MedicalAsset(
            hospital_id=hospital.id,
            area_id=areas[area_code].id,
            inventory_code=inv,
            serial_number=serial,
            brand=brand,
            model=model,
            device_type=dtype,
            risk_class=risk,
            acquisition_date=today - timedelta(days=900),
            replacement_cost=cost,
            preventive_interval_days=interval,
            last_service_date=last_svc,
            next_preventive_date=next_prev,
            current_state="OPERATIVO",
        )
        db.session.add(asset)
        db.session.flush()
        created_assets[inv] = asset

    # 7. Historical Incidents, Work Orders, Certifications & Audit Chains
    # A) Scenario 3: Defibrillator URG-DES-01 calibrated 7 days ago with full double-signed certification
    desf = created_assets["URG-DES-01"]
    t_desf = now - timedelta(days=7, hours=6)
    inc_desf = IncidentReport(
        hospital_id=hospital.id,
        asset_id=desf.id,
        event_type="PREVENTIVO_PROGRAMADO",
        severity="BAJA",
        symptom_text="Mantenimiento preventivo y prueba de descarga metrológica (30J/200J)",
        reported_by_id=users["BIOMEDICO"].id,
        created_at=t_desf,
    )
    db.session.add(inc_desf)
    db.session.flush()
    wo_desf = WorkOrder(
        hospital_id=hospital.id,
        incident_report_id=inc_desf.id,
        asset_id=desf.id,
        biomedical_user_id=users["BIOMEDICO"].id,
        service_type="PREVENTIVO",
        technical_diagnosis="Verificación de capacitor, electrodos y energía de descarga dentro de ±2% (NOM-016-SSA3-2012).",
        parts_used="Kit de electrodos de prueba y gel conductor",
        parts_cost=320.0,
        started_at=t_desf,
        closed_at=t_desf + timedelta(hours=3),
        status="CERRADA",
    )
    db.session.add(wo_desf)
    db.session.flush()
    folio_desf = generate_unique_folio(today.year)
    cert_desf = Certification(
        hospital_id=hospital.id,
        work_order_id=wo_desf.id,
        asset_id=desf.id,
        folio_biotrack=folio_desf,
        external_lab_folio="CENAM-EXT-2026-8841",
        metrological_result="APROBADO: Descarga 30J=29.9J, 200J=199.4J; tiempo de carga 4.1s.",
        service_date=today - timedelta(days=7),
        expiration_date=today + timedelta(days=173),
        biomedical_signer_id=users["BIOMEDICO"].id,
        biomedical_signed_at=t_desf + timedelta(hours=2),
        biomedical_signature_hash=_sig_hash(users["BIOMEDICO"], f"FIRMA1|{folio_desf}", t_desf + timedelta(hours=2)),
        area_receiver_id=users["RESPONSABLE_AREA"].id,
        area_received_at=t_desf + timedelta(hours=3),
        area_signature_hash=_sig_hash(users["RESPONSABLE_AREA"], f"FIRMA2|{folio_desf}", t_desf + timedelta(hours=3)),
        public_qr_token="demo-qr-desf-01",
    )
    db.session.add(cert_desf)
    db.session.flush()
    record_audit_event(
        hospital_id=hospital.id,
        asset_id=desf.id,
        event_type="CERTIFICATION_FIRMA1_BIOMEDICAL",
        actor_user_id=users["BIOMEDICO"].id,
        payload={"folio_biotrack": folio_desf, "external_lab_folio": "CENAM-EXT-2026-8841", "result": cert_desf.metrological_result},
        timestamp_utc=t_desf + timedelta(hours=2),
    )
    record_audit_event(
        hospital_id=hospital.id,
        asset_id=desf.id,
        event_type="RECEPTION_FIRMA2_AREA_OPERATIVE",
        actor_user_id=users["RESPONSABLE_AREA"].id,
        payload={"folio_biotrack": folio_desf, "public_qr_token": cert_desf.public_qr_token, "new_state": "OPERATIVO"},
        timestamp_utc=t_desf + timedelta(hours=3),
    )

    # B) Scenario 4: Anesthesia Machines QRF-ANE-01 & QRF-ANE-02 with high failures, >40% downtime, parts cost > replacement
    for inv_code, count_fails, cost_each, down_hours in [
        ("QRF-ANE-01", 6, 5200.0, 620),
        ("QRF-ANE-02", 5, 4800.0, 580),
        ("LAB-CEN-01", 3, 1450.0, 24),
        ("URG-MON-05", 2, 650.0, 12),
    ]:
        asset = created_assets[inv_code]
        for idx in range(count_fails):
            t_start = now - timedelta(days=300 - idx * 42)
            t_end = t_start + timedelta(hours=down_hours)
            inc = IncidentReport(
                hospital_id=hospital.id,
                asset_id=asset.id,
                event_type="FALLA_CORRECTIVA",
                severity="CRITICA" if "ANE" in inv_code else "MEDIA",
                symptom_text="Fuga en circuito respiratorio / desgaste de válvula y sensores"
                if "ANE" in inv_code
                else "Desviación de sensor / componente desgastado",
                reported_by_id=users["CLINICO"].id,
                created_at=t_start,
            )
            db.session.add(inc)
            db.session.flush()
            wo = WorkOrder(
                hospital_id=hospital.id,
                incident_report_id=inc.id,
                asset_id=asset.id,
                biomedical_user_id=users["BIOMEDICO"].id,
                service_type="CORRECTIVO",
                technical_diagnosis="Sustitución de ensamble neumático / sensores y recalibración.",
                parts_used="Kit de sellos, celda de O2, sensor de flujo",
                parts_cost=cost_each,
                started_at=t_start + timedelta(hours=1),
                closed_at=t_end,
                status="CERRADA",
            )
            db.session.add(wo)
            db.session.flush()
            folio = generate_unique_folio(t_end.year)
            cert = Certification(
                hospital_id=hospital.id,
                work_order_id=wo.id,
                asset_id=asset.id,
                folio_biotrack=folio,
                metrological_result="Prueba funcional y de fugas aprobada post-reparación.",
                service_date=t_end.date(),
                expiration_date=t_end.date() + timedelta(days=180),
                biomedical_signer_id=users["BIOMEDICO"].id,
                biomedical_signed_at=t_end - timedelta(hours=1),
                biomedical_signature_hash=_sig_hash(users["BIOMEDICO"], f"FIRMA1|{folio}", t_end - timedelta(hours=1)),
                area_receiver_id=users["RESPONSABLE_AREA"].id,
                area_received_at=t_end,
                area_signature_hash=_sig_hash(users["RESPONSABLE_AREA"], f"FIRMA2|{folio}", t_end),
                public_qr_token=secrets.token_urlsafe(14),
            )
            db.session.add(cert)
            db.session.flush()
            record_audit_event(
                hospital_id=hospital.id,
                asset_id=asset.id,
                event_type="INCIDENT_REPORTED",
                actor_user_id=users["CLINICO"].id,
                payload={"incident_id": inc.id, "severity": inc.severity, "symptom": inc.symptom_text},
                timestamp_utc=t_start,
            )
            record_audit_event(
                hospital_id=hospital.id,
                asset_id=asset.id,
                event_type="RECEPTION_FIRMA2_AREA_OPERATIVE",
                actor_user_id=users["RESPONSABLE_AREA"].id,
                payload={"folio_biotrack": folio, "parts_cost": cost_each},
                timestamp_utc=t_end,
            )

    db.session.commit()
    install_mariadb_immutability_triggers()
