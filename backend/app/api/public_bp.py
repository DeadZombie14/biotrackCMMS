from datetime import date
from flask import Blueprint, Response, current_app, jsonify
from app.models import Certification, Hospital
from app.services.qr_service import generate_qr_svg

public_bp = Blueprint("public", __name__, url_prefix="/api/v1/public")


@public_bp.get("/verify/<string:qr_token>")
def public_verify(qr_token: str):
    """
    Public, unauthenticated QR verification endpoint (AD-08).
    Shows maintenance validity & status WITHOUT exposing internal patient/staff/hospital secrets.
    """
    cert = Certification.query.filter_by(public_qr_token=qr_token).first()
    if not cert:
        return jsonify({"error": "Código de verificación no encontrado."}), 404

    asset = cert.asset
    hospital = Hospital.query.get(cert.hospital_id)
    today = date.today()
    is_expired = cert.expiration_date < today if cert.expiration_date else True
    is_operative = asset.current_state == "OPERATIVO" and not is_expired and bool(cert.area_signature_hash)

    return jsonify(
        {
            "folio_biotrack": cert.folio_biotrack,
            "hospital_name": hospital.name if hospital else None,
            "device_type": asset.device_type,
            "brand": asset.brand,
            "model": asset.model,
            "inventory_code": asset.inventory_code,
            "current_state": asset.current_state,
            "service_date": cert.service_date.isoformat() if cert.service_date else None,
            "expiration_date": cert.expiration_date.isoformat() if cert.expiration_date else None,
            "is_valid_for_clinical_use": is_operative,
            "is_expired": is_expired,
            "double_signed": bool(cert.biomedical_signature_hash and cert.area_signature_hash),
            "external_lab_folio": cert.external_lab_folio,
        }
    )


@public_bp.get("/sticker/<string:qr_token>/qr.svg")
def sticker_qr_svg(qr_token: str):
    cert = Certification.query.filter_by(public_qr_token=qr_token).first_or_404()
    frontend_url = current_app.config.get("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    verify_url = f"{frontend_url}/verify/{cert.public_qr_token}"
    svg = generate_qr_svg(verify_url)
    return Response(svg, mimetype="image/svg+xml")
