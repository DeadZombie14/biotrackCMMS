from flask import Blueprint, jsonify
from app.models import AuditEvent, Certification, IncidentReport, MedicalAsset, WorkOrder
from app.services.audit_service import verify_asset_audit_chain
from app.services.auth_service import get_current_user, roles_required

audit_bp = Blueprint("audit", __name__, url_prefix="/api/v1/audit")


@audit_bp.get("/assets/<string:identifier>")
@roles_required("AUDITOR", "DIRECCION", "JEFE_TALLER")
def get_asset_dossier(identifier: str):
    """
    Strictly read-only audit dossier by serial number, inventory code, or numeric ID (QA-05).
    """
    user = get_current_user()
    asset = None
    if identifier.isdigit():
        asset = MedicalAsset.query.filter_by(
            id=int(identifier), hospital_id=user.hospital_id
        ).first()
    if not asset:
        asset = MedicalAsset.query.filter(
            MedicalAsset.hospital_id == user.hospital_id,
            (MedicalAsset.serial_number == identifier)
            | (MedicalAsset.inventory_code == identifier),
        ).first()
    if not asset:
        return jsonify({"error": f"Activo '{identifier}' no encontrado."}), 404

    events = (
        AuditEvent.query.filter_by(asset_id=asset.id)
        .order_by(AuditEvent.id.asc())
        .all()
    )
    incidents = (
        IncidentReport.query.filter_by(asset_id=asset.id)
        .order_by(IncidentReport.created_at.desc())
        .all()
    )
    certifications = (
        Certification.query.filter_by(asset_id=asset.id)
        .order_by(Certification.id.desc())
        .all()
    )
    integrity = verify_asset_audit_chain(asset.id)

    return jsonify(
        {
            "asset": asset.to_dict(),
            "integrity": integrity,
            "audit_events": [e.to_dict() for e in events],
            "incidents": [i.to_dict() for i in incidents],
            "certifications": [c.to_dict() for c in certifications],
        }
    )


@audit_bp.get("/assets/<int:asset_id>/verify")
@roles_required("AUDITOR", "DIRECCION", "JEFE_TALLER")
def verify_chain(asset_id: int):
    user = get_current_user()
    asset = MedicalAsset.query.filter_by(id=asset_id, hospital_id=user.hospital_id).first_or_404()
    integrity = verify_asset_audit_chain(asset.id)
    return jsonify({"asset_id": asset.id, "serial_number": asset.serial_number, "integrity": integrity})
