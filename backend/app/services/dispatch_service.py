import json
import queue
import threading
from datetime import datetime, timedelta, timezone
from flask import current_app
from app.extensions import db
from app.models import DispatchAlert, MedicalAsset, OnCallRoster, User
from app.services.audit_service import record_audit_event


class SSEBroker:
    """Lightweight in-memory Server-Sent Events hub for instant console & floor alerts."""

    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers: list[queue.Queue] = []

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=50)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def publish(self, event_name: str, data: dict):
        payload = f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        with self._lock:
            dead = []
            for q in self._subscribers:
                try:
                    q.put_nowait(payload)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)


sse_broker = SSEBroker()


def find_on_call_biomedical(hospital_id: int, area_id: int) -> User | None:
    """Locate the currently active on-call biomedical engineer covering the area (AD-05)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rosters = (
        OnCallRoster.query.filter_by(hospital_id=hospital_id, is_active=True)
        .filter(OnCallRoster.start_time <= now, OnCallRoster.end_time >= now)
        .all()
    )
    for roster in rosters:
        areas = roster.coverage_areas_json or []
        if not areas or area_id in areas:
            if roster.biomedical_user and roster.biomedical_user.is_active:
                return roster.biomedical_user

    # Fallback: any active on-call roster entry or any active BIOMEDICO
    any_roster = OnCallRoster.query.filter_by(hospital_id=hospital_id, is_active=True).first()
    if any_roster and any_roster.biomedical_user:
        return any_roster.biomedical_user

    return (
        User.query.filter_by(hospital_id=hospital_id, role="BIOMEDICO", is_active=True).first()
        or User.query.filter_by(hospital_id=hospital_id, role="JEFE_TALLER", is_active=True).first()
    )


def create_critical_dispatch_alert(
    *,
    asset: MedicalAsset,
    incident_report_id: int,
    symptom_text: str,
    actor_user_id: int,
    timeout_seconds: int | None = None,
) -> DispatchAlert:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    timeout = (
        timeout_seconds
        if timeout_seconds is not None
        else current_app.config.get("ESCALATION_TIMEOUT_SECONDS", 600)
    )
    on_call_user = find_on_call_biomedical(asset.hospital_id, asset.area_id)
    area_name = asset.area.name if asset.area else f"Área #{asset.area_id}"
    msg = (
        f"ALERTA CRÍTICA FAIL-SAFE: {asset.device_type} [{asset.inventory_code}] "
        f"en {area_name} BLOQUEADO. Síntoma: {symptom_text}."
    )
    alert = DispatchAlert(
        hospital_id=asset.hospital_id,
        incident_report_id=incident_report_id,
        asset_id=asset.id,
        assigned_biomedical_id=on_call_user.id if on_call_user else None,
        status="PENDIENTE",
        channel="CONSOLA+MENSAJE_DIRECTO",
        message_body=msg,
        dispatched_at=now,
        ack_deadline_at=now + timedelta(seconds=timeout),
    )
    db.session.add(alert)
    db.session.flush()

    record_audit_event(
        hospital_id=asset.hospital_id,
        asset_id=asset.id,
        event_type="ALERT_DISPATCHED_ONCALL",
        actor_user_id=actor_user_id,
        payload={
            "alert_id": alert.id,
            "assigned_biomedical_id": alert.assigned_biomedical_id,
            "assigned_biomedical_name": on_call_user.full_name if on_call_user else None,
            "ack_deadline_at": alert.ack_deadline_at.isoformat(),
            "channel": alert.channel,
        },
    )
    return alert


def escalate_overdue_alerts(hospital_id: int | None = None) -> list[DispatchAlert]:
    """Escalate unacknowledged critical alerts past ack_deadline_at to JEFE_TALLER (QA-07)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    query = DispatchAlert.query.filter(
        DispatchAlert.status == "PENDIENTE",
        DispatchAlert.ack_deadline_at <= now,
    )
    if hospital_id:
        query = query.filter_by(hospital_id=hospital_id)

    overdue = query.with_for_update().all()
    escalated_list = []
    for alert in overdue:
        chief = User.query.filter_by(
            hospital_id=alert.hospital_id, role="JEFE_TALLER", is_active=True
        ).first()
        alert.status = "ESCALADO"
        alert.escalated_at = now
        if chief:
            alert.escalated_to_id = chief.id
        record_audit_event(
            hospital_id=alert.hospital_id,
            asset_id=alert.asset_id,
            event_type="ALERT_ESCALATED_CHIEF",
            actor_user_id=chief.id if chief else (alert.assigned_biomedical_id or 1),
            payload={
                "alert_id": alert.id,
                "escalated_to_id": alert.escalated_to_id,
                "escalated_to_name": chief.full_name if chief else None,
                "reason": "Sin acuse de recibo del biomédico de guardia dentro del SLA.",
            },
        )
        escalated_list.append(alert)

    if escalated_list:
        db.session.commit()
        for alert in escalated_list:
            sse_broker.publish("alert_escalated", alert.to_dict())

    return escalated_list
