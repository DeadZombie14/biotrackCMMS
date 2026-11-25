import queue
from datetime import datetime, timezone
from flask import Blueprint, Response, jsonify, request, stream_with_context
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models import DispatchAlert, OnCallRoster
from app.services.audit_service import record_audit_event
from app.services.auth_service import get_current_user, roles_required
from app.services.dispatch_service import escalate_overdue_alerts, sse_broker

oncall_bp = Blueprint("oncall", __name__, url_prefix="/api/v1")


@oncall_bp.get("/oncall/roster")
@jwt_required()
def list_roster():
    user = get_current_user()
    rosters = (
        OnCallRoster.query.filter_by(hospital_id=user.hospital_id)
        .order_by(OnCallRoster.is_active.desc(), OnCallRoster.start_time.desc())
        .all()
    )
    return jsonify({"rosters": [r.to_dict() for r in rosters]})


@oncall_bp.post("/oncall/roster")
@roles_required("BIOMEDICO", "JEFE_TALLER")
def create_roster():
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    if not data.get("biomedical_user_id") or not data.get("start_time") or not data.get("end_time"):
        return jsonify({"error": "Seleccione especialista y rango de horario de guardia."}), 400

    roster = OnCallRoster(
        hospital_id=user.hospital_id,
        biomedical_user_id=int(data["biomedical_user_id"]),
        coverage_areas_json=data.get("coverage_areas", []),
        start_time=datetime.fromisoformat(data["start_time"]),
        end_time=datetime.fromisoformat(data["end_time"]),
        contact_phone=(data.get("contact_phone") or user.phone or "33-0000-0000").strip(),
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(roster)
    db.session.commit()
    return jsonify({"roster": roster.to_dict()}), 201


@oncall_bp.patch("/oncall/roster/<int:roster_id>")
@roles_required("BIOMEDICO", "JEFE_TALLER")
def toggle_roster(roster_id: int):
    user = get_current_user()
    roster = OnCallRoster.query.filter_by(id=roster_id, hospital_id=user.hospital_id).first_or_404()
    data = request.get_json(silent=True) or {}
    if "is_active" in data:
        roster.is_active = bool(data["is_active"])
    if "contact_phone" in data:
        roster.contact_phone = data["contact_phone"]
    db.session.commit()
    return jsonify({"roster": roster.to_dict()})


@oncall_bp.get("/alerts")
@jwt_required()
def list_alerts():
    user = get_current_user()
    # Check escalations opportunistically on poll
    escalate_overdue_alerts(hospital_id=user.hospital_id)
    alerts = (
        DispatchAlert.query.filter_by(hospital_id=user.hospital_id)
        .order_by(DispatchAlert.dispatched_at.desc())
        .limit(40)
        .all()
    )
    return jsonify({"alerts": [a.to_dict() for a in alerts]})


@oncall_bp.post("/alerts/<int:alert_id>/ack")
@roles_required("BIOMEDICO", "JEFE_TALLER")
def acknowledge_alert(alert_id: int):
    user = get_current_user()
    alert = DispatchAlert.query.filter_by(id=alert_id, hospital_id=user.hospital_id).first_or_404()
    if alert.status in ("ACUSADO", "RESUELTO"):
        return jsonify({"alert": alert.to_dict()})

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    alert.status = "ACUSADO"
    alert.acknowledged_at = now
    record_audit_event(
        hospital_id=alert.hospital_id,
        asset_id=alert.asset_id,
        event_type="ALERT_ACKNOWLEDGED",
        actor_user_id=user.id,
        payload={"alert_id": alert.id, "acknowledged_by": user.full_name},
    )
    db.session.commit()
    sse_broker.publish("alert_acknowledged", alert.to_dict())
    return jsonify({"alert": alert.to_dict()})


@oncall_bp.post("/alerts/check-escalations")
@jwt_required()
def trigger_escalation_check():
    user = get_current_user()
    escalated = escalate_overdue_alerts(hospital_id=user.hospital_id)
    return jsonify({"escalated_count": len(escalated), "escalated": [a.to_dict() for a in escalated]})


@oncall_bp.get("/alerts/stream")
def alerts_stream():
    """Server-Sent Events stream for real-time Fail-Safe & workshop notifications (AD-05)."""

    def event_stream():
        q = sse_broker.subscribe()
        try:
            yield "event: connected\ndata: {\"status\": \"ok\"}\n\n"
            while True:
                try:
                    msg = q.get(timeout=20)
                    yield msg
                except queue.Empty:
                    yield ": heartbeat\n\n"
        finally:
            sse_broker.unsubscribe(q)

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
