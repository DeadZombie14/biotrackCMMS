from flask import Blueprint, jsonify
from app.services.analytics_service import compute_executive_kpis
from app.services.auth_service import get_current_user, roles_required

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/v1/analytics")


@analytics_bp.get("/kpis")
@roles_required("DIRECCION", "JEFE_TALLER", "AUDITOR", "BIOMEDICO")
def get_kpis():
    user = get_current_user()
    data = compute_executive_kpis(user.hospital_id)
    return jsonify(data)
