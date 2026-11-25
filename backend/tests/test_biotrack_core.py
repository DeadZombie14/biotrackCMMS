import time
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError, InternalError
from app.extensions import db
from app.models import AuditEvent, DispatchAlert, MedicalAsset
from tests.conftest import auth_headers


def test_failsafe_critical_block_and_oncall_dispatch(client):
    """QA-01 & QA-07: Critical report atomically blocks asset (< 2s) and dispatches on-call alert."""
    clinico = auth_headers(client, "clinico@biotrack.mx")
    assets = client.get("/api/v1/assets?q=UCI-BOM-01", headers=clinico).get_json()["assets"]
    pump = assets[0]
    assert pump["current_state"] == "OPERATIVO"

    t0 = time.perf_counter()
    resp = client.post(
        "/api/v1/incidents",
        headers=clinico,
        json={
            "asset_id": pump["id"],
            "severity": "CRITICA",
            "symptom_text": "Detención súbita sin causa mecánica aparente",
        },
    )
    elapsed = time.perf_counter() - t0
    assert resp.status_code == 201
    assert elapsed < 2.0
    body = resp.get_json()
    assert body["failsafe_triggered"] is True
    assert body["asset"]["current_state"] == "BLOQUEADO"
    assert body["dispatch_alert"] is not None
    assert body["dispatch_alert"]["status"] == "PENDIENTE"


def test_two_person_rule_and_public_qr_verification(client):
    """QA-06, AD-03, AD-08: Full lifecycle with re-auth Firma 1 + Firma 2 + unique folio + public QR."""
    clinico = auth_headers(client, "clinico@biotrack.mx")
    biomed = auth_headers(client, "biomedico@biotrack.mx")
    resp_area = auth_headers(client, "responsable@biotrack.mx")

    pump = client.get("/api/v1/assets?q=UCI-BOM-02", headers=clinico).get_json()["assets"][0]

    # 1. Critical failure -> BLOQUEADO
    inc_res = client.post(
        "/api/v1/incidents",
        headers=clinico,
        json={
            "asset_id": pump["id"],
            "severity": "CRITICA",
            "symptom_text": "Desviación en tasa de infusión",
        },
    ).get_json()
    wo_id = inc_res["work_order"]["id"]

    # 2. Take work order -> EN_DIAGNOSTICO
    assert client.post(f"/api/v1/work-orders/{wo_id}/take", headers=biomed).status_code == 200

    # 3. Illegal skip: try certifying directly from EN_DIAGNOSTICO without EN_CALIBRACION
    skip_res = client.post(
        f"/api/v1/work-orders/{wo_id}/certify",
        headers=biomed,
        json={"reauth_password": "BioTrack2026!", "metrological_result": "OK"},
    )
    assert skip_res.status_code == 409

    # 4. Move to EN_CALIBRACION with diagnosis & parts
    upd = client.patch(
        f"/api/v1/work-orders/{wo_id}",
        headers=biomed,
        json={
            "technical_diagnosis": "Sensor de flujo reemplazado",
            "parts_used": "Sensor Baxter OEM",
            "parts_cost": 450.0,
            "target_state": "EN_CALIBRACION",
        },
    )
    assert upd.status_code == 200

    # 5. Firma 1 rejects bad password
    bad_pw = client.post(
        f"/api/v1/work-orders/{wo_id}/certify",
        headers=biomed,
        json={"reauth_password": "WrongPassword", "metrological_result": "Flujo 100 mL/h ±1%"},
    )
    assert bad_pw.status_code == 401

    # 6. Firma 1 succeeds -> CERTIFICADO_PENDIENTE_RECEPCION + Folio CAL-YYYY-XXXXX
    f1 = client.post(
        f"/api/v1/work-orders/{wo_id}/certify",
        headers=biomed,
        json={
            "reauth_password": "BioTrack2026!",
            "metrological_result": "Flujo 100 mL/h ±0.8% aprobado",
            "external_lab_folio": "LAB-EXT-9001",
        },
    )
    assert f1.status_code == 201
    cert = f1.get_json()["certification"]
    assert cert["folio_biotrack"].startswith("CAL-")
    assert f1.get_json()["work_order"]["asset"]["current_state"] == "CERTIFICADO_PENDIENTE_RECEPCION"

    # 7. Biomedical engineer CANNOT unilaterally execute Firma 2 (Two-Person Rule)
    unilateral = client.post(
        f"/api/v1/work-orders/{wo_id}/receive",
        headers=biomed,
        json={"reauth_password": "BioTrack2026!"},
    )
    assert unilateral.status_code == 403

    # 7b. Area Responsible with wrong password gets clear 401 Firma incorrecta
    bad_f2 = client.post(
        f"/api/v1/work-orders/{wo_id}/receive",
        headers=resp_area,
        json={"reauth_password": "WrongPassword"},
    )
    assert bad_f2.status_code == 401
    assert "Firma incorrecta" in bad_f2.get_json()["error"]

    # 8. Area Responsible executes Firma 2 -> OPERATIVO
    f2 = client.post(
        f"/api/v1/work-orders/{wo_id}/receive",
        headers=resp_area,
        json={"reauth_password": "BioTrack2026!", "reception_notes": "Verificado físicamente en UCI"},
    )
    assert f2.status_code == 200
    assert f2.get_json()["work_order"]["asset"]["current_state"] == "OPERATIVO"
    qr_token = f2.get_json()["certification"]["public_qr_token"]

    # 9. Public QR verification works WITHOUT authentication
    pub = client.get(f"/api/v1/public/verify/{qr_token}")
    assert pub.status_code == 200
    pub_data = pub.get_json()
    assert pub_data["is_valid_for_clinical_use"] is True
    assert pub_data["folio_biotrack"] == cert["folio_biotrack"]
    assert pub_data["double_signed"] is True

    # 10. QR SVG renders cleanly
    svg = client.get(f"/api/v1/public/sticker/{qr_token}/qr.svg")
    assert svg.status_code == 200
    assert b"<svg" in svg.data


def test_audit_immutability_triggers_and_sha256_verification(app, client):
    """QA-03 & QA-05: MariaDB triggers reject UPDATE/DELETE on audit_events; chain verifies intact."""
    auditor = auth_headers(client, "auditor@cofepris.mx")
    dossier = client.get("/api/v1/audit/assets/ZOL-RSP-2022-001", headers=auditor)
    assert dossier.status_code == 200
    body = dossier.get_json()
    assert body["integrity"]["valid"] is True
    assert body["integrity"]["total_events"] >= 2
    assert all(e["event_type"] != "ASSET_REGISTERED" for e in body["audit_events"])

    # Attempt direct SQL UPDATE on audit_events -> must be rejected by MariaDB trigger
    with app.app_context():
        ev = AuditEvent.query.first()
        with pytest.raises((OperationalError, ProgrammingError, InternalError)):
            db.session.execute(
                text("UPDATE audit_events SET event_type = 'TAMPERED' WHERE id = :id"),
                {"id": ev.id},
            )
        db.session.rollback()

        with pytest.raises((OperationalError, ProgrammingError, InternalError)):
            db.session.execute(
                text("DELETE FROM audit_events WHERE id = :id"),
                {"id": ev.id},
            )
        db.session.rollback()


def test_oncall_escalation_to_workshop_chief(app, client):
    """QA-07: Unacknowledged critical alert escalates to JEFE_TALLER past deadline."""
    clinico = auth_headers(client, "clinico@biotrack.mx")
    jefe = auth_headers(client, "jefe.taller@biotrack.mx")

    pump = client.get("/api/v1/assets?q=UCI-BOM-01", headers=clinico).get_json()["assets"][0]
    res = client.post(
        "/api/v1/incidents",
        headers=clinico,
        json={
            "asset_id": pump["id"],
            "severity": "CRITICA",
            "symptom_text": "Falla crítica de prueba de escalamiento",
            "escalation_timeout_seconds": 0,
        },
    )
    assert res.status_code == 201
    alert_id = res.get_json()["dispatch_alert"]["id"]

    # Force deadline into past & run escalation check
    with app.app_context():
        al = db.session.get(DispatchAlert, alert_id)
        al.ack_deadline_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=10)
        db.session.commit()

    esc = client.post("/api/v1/alerts/check-escalations", headers=jefe)
    assert esc.status_code == 200
    assert esc.get_json()["escalated_count"] == 1
    assert esc.get_json()["escalated"][0]["status"] == "ESCALADO"


def test_executive_kpis_and_preventive_due(client):
    """Scenario 4 & 5: Verify all 5 ConOps v0.2 KPIs and 3 ICU ventilators due soon."""
    direccion = auth_headers(client, "direccion@biotrack.mx")
    biomed = auth_headers(client, "biomedico@biotrack.mx")

    kpis = client.get("/api/v1/analytics/kpis", headers=direccion)
    assert kpis.status_code == 200
    data = kpis.get_json()
    assert data["summary"]["replacement_candidates_count"] >= 2
    assert len(data["availability_by_area"]) == 4
    assert data["summary"]["mttr_hours"] > 0

    due = client.get("/api/v1/assets/preventive-due?days=15", headers=biomed).get_json()["assets"]
    ven_codes = [a["inventory_code"] for a in due if a["inventory_code"].startswith("UCI-VEN")]
    assert len(ven_codes) == 3


def test_false_positive_dismissal_does_not_affect_metrics(client):
    """False positive dismissed by biomedical returns asset to OPERATIVO without penalizing KPIs."""
    clinico = auth_headers(client, "clinico@biotrack.mx")
    biomed = auth_headers(client, "biomedico@biotrack.mx")
    direccion = auth_headers(client, "direccion@biotrack.mx")

    pump = client.get("/api/v1/assets?q=UCI-BOM-01", headers=clinico).get_json()["assets"][0]
    inc = client.post(
        "/api/v1/incidents",
        headers=clinico,
        json={"asset_id": pump["id"], "severity": "CRITICA", "symptom_text": "Falsa alarma de oclusión"},
    ).get_json()
    wo_id = inc["work_order"]["id"]

    fp = client.post(
        f"/api/v1/work-orders/{wo_id}/false-positive",
        headers=biomed,
        json={"reason": "Manguera pinzada externamente; bomba 100% operativa tras revisión."},
    )
    assert fp.status_code == 200
    assert fp.get_json()["work_order"]["status"] == "FALSO_POSITIVO"
    assert fp.get_json()["work_order"]["asset"]["current_state"] == "OPERATIVO"

    kpis = client.get("/api/v1/analytics/kpis", headers=direccion).get_json()
    assert kpis["summary"]["false_positives_dismissed"] == 1
    pump_metric = next(m for m in kpis["cost_vs_replacement"] if m["asset_id"] == pump["id"])
    assert pump_metric["failure_count"] == 0


def test_firma2_rejection_returns_to_workshop(client):
    """Area Responsible (Firma 2) can reject handoff and send asset back to EN_DIAGNOSTICO."""
    clinico = auth_headers(client, "clinico@biotrack.mx")
    biomed = auth_headers(client, "biomedico@biotrack.mx")
    resp_area = auth_headers(client, "responsable@biotrack.mx")

    mon = client.get("/api/v1/assets?q=URG-MON-04", headers=clinico).get_json()["assets"][0]
    wo_id = client.post(
        "/api/v1/incidents",
        headers=clinico,
        json={"asset_id": mon["id"], "severity": "MEDIA", "symptom_text": "Lectura NIBP errática"},
    ).get_json()["work_order"]["id"]

    client.post(f"/api/v1/work-orders/{wo_id}/take", headers=biomed)
    client.patch(f"/api/v1/work-orders/{wo_id}", headers=biomed, json={"target_state": "EN_CALIBRACION"})
    client.post(
        f"/api/v1/work-orders/{wo_id}/certify",
        headers=biomed,
        json={"reauth_password": "BioTrack2026!", "metrological_result": "OK"},
    )

    rej = client.post(
        f"/api/v1/work-orders/{wo_id}/reject-reception",
        headers=resp_area,
        json={"rejection_reason": "Falta brazalete pediátrico y cable SpO2 presenta falso contacto."},
    )
    assert rej.status_code == 200
    wo_data = rej.get_json()["work_order"]
    assert wo_data["asset"]["current_state"] == "EN_DIAGNOSTICO"
    assert "RECHAZADO EN RECEPCIÓN" in wo_data["technical_diagnosis"]
    assert wo_data["certification"] is None
