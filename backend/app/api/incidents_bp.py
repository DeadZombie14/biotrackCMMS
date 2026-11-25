from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from app.models import IncidentReport, MedicalAsset, SymptomCatalog
from app.services.auth_service import get_current_user, roles_required
from app.services.state_machine import StateTransitionError, report_incident_atomic

incidents_bp = Blueprint("incidents", __name__, url_prefix="/api/v1/incidents")


@incidents_bp.get("")
@jwt_required()
def list_incidents():
    user = get_current_user()
    limit = request.args.get("limit", default=50, type=int)
    incidents = (
        IncidentReport.query.filter_by(hospital_id=user.hospital_id)
        .order_by(IncidentReport.created_at.desc())
        .limit(limit)
        .all()
    )
    return jsonify({"incidents": [i.to_dict() for i in incidents]})


@incidents_bp.post("")
@roles_required("CLINICO", "RESPONSABLE_AREA", "BIOMEDICO", "JEFE_TALLER")
def create_incident():
    """
    3-Step Floor Terminal Report (< 30s, QA-02) + Atomic Fail-Safe Block (< 2s, QA-01).
    No free-text required when selecting a symptom from the closed catalog.
    """
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    asset_id = data.get("asset_id")
    if not asset_id:
        return jsonify({"error": "Seleccione un equipo médico."}), 400

    asset = MedicalAsset.query.filter_by(id=int(asset_id), hospital_id=user.hospital_id).first()
    if not asset:
        return jsonify({"error": "Equipo médico no encontrado."}), 404

    symptom_id = data.get("symptom_id")
    symptom_text = (data.get("symptom_text") or "").strip()
    severity = (data.get("severity") or "").strip().upper()

    if symptom_id:
        cat = SymptomCatalog.query.get(int(symptom_id))
        if cat:
            symptom_text = symptom_text or cat.description
            severity = severity or cat.default_severity

    if not symptom_text:
        return jsonify({"error": "Seleccione un síntoma del catálogo tipificado."}), 400
    if not severity:
        severity = "MEDIA"

    is_deferred = bool(data.get("is_deferred", False))
    declared_at = None
    if is_deferred and data.get("declared_occurred_at"):
        declared_at = datetime.fromisoformat(data["declared_occurred_at"])

    timeout_override = data.get("escalation_timeout_seconds")
    if timeout_override is not None:
        timeout_override = int(timeout_override)

    try:
        incident, wo, alert = report_incident_atomic(
            asset=asset,
            actor=user,
            severity=severity,
            symptom_text=symptom_text,
            symptom_id=int(symptom_id) if symptom_id else None,
            notes=data.get("notes"),
            terminal_ip=request.remote_addr,
            is_deferred=is_deferred,
            declared_occurred_at=declared_at,
            escalation_timeout_override=timeout_override,
        )
    except StateTransitionError as exc:
        return jsonify({"error": exc.message}), exc.status_code

    return (
        jsonify(
            {
                "incident": incident.to_dict(),
                "work_order": wo.to_dict(),
                "asset": asset.to_dict(),
                "dispatch_alert": alert.to_dict() if alert else None,
                "failsafe_triggered": asset.current_state == "BLOQUEADO",
            }
        ),
        201,
    )
