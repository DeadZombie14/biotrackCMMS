from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from app.models import MedicalAsset, WorkOrder
from app.services.auth_service import get_current_user, roles_required, verify_reauth
from app.services.state_machine import (
    StateTransitionError,
    certify_work_order_firma1,
    confirm_reception_firma2,
    dismiss_false_positive,
    reject_reception_firma2,
    take_work_order,
    transition_work_order_diagnosis,
)

work_orders_bp = Blueprint("work_orders", __name__, url_prefix="/api/v1/work-orders")


@work_orders_bp.get("")
@jwt_required()
def list_work_orders():
    user = get_current_user()
    status = request.args.get("status")
    pending_reception = request.args.get("pending_reception") == "true"

    query = WorkOrder.query.filter_by(hospital_id=user.hospital_id)
    if pending_reception:
        query = query.filter_by(status="CERTIFICADA")
    elif status:
        query = query.filter_by(status=status)

    orders = query.order_by(WorkOrder.id.desc()).all()
    # Pin critical/blocked orders first for biomedical workshop triage
    orders.sort(
        key=lambda o: (
            0 if (o.asset and o.asset.current_state == "BLOQUEADO") else 1,
            0 if (o.asset and o.asset.has_critical_flag) else 1,
            -o.id,
        )
    )
    return jsonify({"work_orders": [o.to_dict() for o in orders]})


@work_orders_bp.post("/<int:wo_id>/take")
@roles_required("BIOMEDICO", "JEFE_TALLER")
def take_order(wo_id: int):
    user = get_current_user()
    wo = WorkOrder.query.filter_by(id=wo_id, hospital_id=user.hospital_id).first_or_404()
    try:
        take_work_order(wo, user)
        return jsonify({"work_order": wo.to_dict()})
    except StateTransitionError as exc:
        return jsonify({"error": exc.message}), exc.status_code


@work_orders_bp.patch("/<int:wo_id>")
@roles_required("BIOMEDICO", "JEFE_TALLER")
def update_order(wo_id: int):
    user = get_current_user()
    wo = WorkOrder.query.filter_by(id=wo_id, hospital_id=user.hospital_id).first_or_404()
    data = request.get_json(silent=True) or {}
    try:
        transition_work_order_diagnosis(
            wo,
            user,
            technical_diagnosis=data.get("technical_diagnosis"),
            parts_used=data.get("parts_used"),
            parts_cost=float(data["parts_cost"]) if data.get("parts_cost") is not None else None,
            target_state=data.get("target_state"),
        )
        return jsonify({"work_order": wo.to_dict()})
    except StateTransitionError as exc:
        return jsonify({"error": exc.message}), exc.status_code


@work_orders_bp.post("/<int:wo_id>/certify")
@roles_required("BIOMEDICO", "JEFE_TALLER")
def certify_firma1(wo_id: int):
    """Firma 1 (Biomedical Engineer): requires password re-authentication (AD-03, AD-06)."""
    user = get_current_user()
    wo = WorkOrder.query.filter_by(id=wo_id, hospital_id=user.hospital_id).first_or_404()
    data = request.get_json(silent=True) or {}

    reauth_password = data.get("reauth_password") or ""
    if not verify_reauth(user, reauth_password):
        return (
            jsonify(
                {
                    "error": "Firma incorrecta: la contraseña institucional no coincide. Verifique e intente nuevamente (Firma 1)."
                }
            ),
            401,
        )

    metrological_result = (data.get("metrological_result") or "").strip()
    if not metrological_result:
        return jsonify({"error": "Registre el resultado de la prueba metrológica."}), 400

    try:
        cert = certify_work_order_firma1(
            wo,
            user,
            metrological_result=metrological_result,
            external_lab_folio=(data.get("external_lab_folio") or "").strip() or None,
            external_cert_note=(data.get("external_cert_note") or "").strip() or None,
        )
        return jsonify({"work_order": wo.to_dict(), "certification": cert.to_dict()}), 201
    except StateTransitionError as exc:
        return jsonify({"error": exc.message}), exc.status_code


@work_orders_bp.post("/<int:wo_id>/receive")
@roles_required("RESPONSABLE_AREA")
def receive_firma2(wo_id: int):
    """Firma 2 (Area Responsible): requires password re-authentication (Two-Person Rule, QA-06)."""
    user = get_current_user()
    wo = WorkOrder.query.filter_by(id=wo_id, hospital_id=user.hospital_id).first_or_404()
    data = request.get_json(silent=True) or {}

    reauth_password = data.get("reauth_password") or ""
    if not verify_reauth(user, reauth_password):
        return (
            jsonify(
                {
                    "error": "Firma incorrecta: la contraseña institucional no coincide. Verifique e intente nuevamente (Firma 2)."
                }
            ),
            401,
        )

    try:
        cert = confirm_reception_firma2(wo, user, reception_notes=data.get("reception_notes"))
        return jsonify({"work_order": wo.to_dict(), "certification": cert.to_dict()})
    except StateTransitionError as exc:
        return jsonify({"error": exc.message}), exc.status_code


@work_orders_bp.post("/<int:wo_id>/false-positive")
@roles_required("BIOMEDICO", "JEFE_TALLER")
def mark_false_positive(wo_id: int):
    """Dismiss a false positive so it does not affect SLA or hospital availability metrics."""
    user = get_current_user()
    wo = WorkOrder.query.filter_by(id=wo_id, hospital_id=user.hospital_id).first_or_404()
    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    if not reason:
        return jsonify({"error": "Indique la justificación técnica del falso positivo."}), 400
    try:
        dismiss_false_positive(wo, user, reason)
        return jsonify({"work_order": wo.to_dict()})
    except StateTransitionError as exc:
        return jsonify({"error": exc.message}), exc.status_code


@work_orders_bp.post("/<int:wo_id>/reject-reception")
@roles_required("RESPONSABLE_AREA")
def reject_reception(wo_id: int):
    """Allow Area Responsible (Firma 2) to reject handoff and send asset back to workshop review."""
    user = get_current_user()
    wo = WorkOrder.query.filter_by(id=wo_id, hospital_id=user.hospital_id).first_or_404()
    data = request.get_json(silent=True) or {}
    reason = (data.get("rejection_reason") or "").strip()
    if not reason:
        return jsonify({"error": "Indique el motivo del rechazo para devolver el equipo a revisión."}), 400
    try:
        reject_reception_firma2(wo, user, reason)
        return jsonify({"work_order": wo.to_dict()})
    except StateTransitionError as exc:
        return jsonify({"error": exc.message}), exc.status_code
