from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required
from app.models import ClinicalArea, Hospital, User
from app.services.auth_service import get_auth_provider, get_current_user

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    identifier = (data.get("email") or data.get("identifier") or "").strip()
    password = data.get("password") or ""
    if not identifier or not password:
        return jsonify({"error": "Ingrese correo/usuario y contraseña."}), 400

    provider = get_auth_provider()
    user = provider.authenticate(identifier, password)
    if not user:
        return jsonify({"error": "Credenciales inválidas o cuenta desactivada."}), 401

    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    hospital = Hospital.query.get(user.hospital_id)
    return jsonify(
        {
            "access_token": token,
            "user": user.to_dict(),
            "hospital": hospital.to_dict() if hospital else None,
        }
    )


@auth_bp.get("/me")
@jwt_required()
def me():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Sesión inválida."}), 401
    hospital = Hospital.query.get(user.hospital_id)
    return jsonify(
        {
            "user": user.to_dict(),
            "hospital": hospital.to_dict() if hospital else None,
        }
    )


@auth_bp.get("/areas")
@jwt_required()
def list_areas():
    user = get_current_user()
    areas = ClinicalArea.query.filter_by(hospital_id=user.hospital_id).order_by(ClinicalArea.id).all()
    return jsonify({"areas": [a.to_dict() for a in areas]})


@auth_bp.get("/biomedical-staff")
@jwt_required()
def list_biomedical_staff():
    user = get_current_user()
    staff = (
        User.query.filter_by(hospital_id=user.hospital_id, is_active=True)
        .filter(User.role.in_(["BIOMEDICO", "JEFE_TALLER"]))
        .order_by(User.full_name)
        .all()
    )
    return jsonify({"staff": [u.to_dict() for u in staff]})
