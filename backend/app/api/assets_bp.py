from datetime import date, timedelta
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models import Certification, MedicalAsset, SymptomCatalog
from app.services.audit_service import record_audit_event
from app.services.auth_service import get_current_user, roles_required
from app.services.state_machine import (
    StateTransitionError,
    record_periodic_inspection,
    start_preventive_maintenance,
)

assets_bp = Blueprint("assets", __name__, url_prefix="/api/v1/assets")


@assets_bp.get("")
@jwt_required()
def list_assets():
    user = get_current_user()
    query = MedicalAsset.query.filter_by(hospital_id=user.hospital_id)

    area_id = request.args.get("area_id", type=int)
    state = request.args.get("state")
    search = request.args.get("q", "").strip()

    if area_id:
        query = query.filter_by(area_id=area_id)
    if state:
        query = query.filter_by(current_state=state)
    if search:
        like = f"%{search}%"
        query = query.filter(
            (MedicalAsset.inventory_code.ilike(like))
            | (MedicalAsset.serial_number.ilike(like))
            | (MedicalAsset.device_type.ilike(like))
            | (MedicalAsset.brand.ilike(like))
            | (MedicalAsset.model.ilike(like))
        )

    assets = query.order_by(MedicalAsset.inventory_code).all()

    # Attach latest certification summary for quick sticker/folio access
    result = []
    for asset in assets:
        d = asset.to_dict()
        latest_cert = (
            Certification.query.filter_by(asset_id=asset.id)
            .order_by(Certification.id.desc())
            .first()
        )
        d["latest_certification"] = latest_cert.to_dict() if latest_cert else None
        result.append(d)

    return jsonify({"assets": result})


@assets_bp.get("/<int:asset_id>")
@jwt_required()
def get_asset(asset_id: int):
    user = get_current_user()
    asset = MedicalAsset.query.filter_by(id=asset_id, hospital_id=user.hospital_id).first_or_404()
    latest_cert = (
        Certification.query.filter_by(asset_id=asset.id)
        .order_by(Certification.id.desc())
        .first()
    )
    d = asset.to_dict()
    d["latest_certification"] = latest_cert.to_dict() if latest_cert else None
    return jsonify({"asset": d})


@assets_bp.post("")
@roles_required("BIOMEDICO", "JEFE_TALLER")
def create_asset():
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    required = [
        "area_id",
        "inventory_code",
        "serial_number",
        "brand",
        "model",
        "device_type",
        "replacement_cost",
    ]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Campos obligatorios faltantes: {', '.join(missing)}"}), 400

    acq_str = data.get("acquisition_date")
    acq_date = date.fromisoformat(acq_str) if acq_str else date.today()
    interval = int(data.get("preventive_interval_days", 180))
    next_prev = (
        date.fromisoformat(data["next_preventive_date"])
        if data.get("next_preventive_date")
        else date.today() + timedelta(days=interval)
    )

    asset = MedicalAsset(
        hospital_id=user.hospital_id,
        area_id=int(data["area_id"]),
        inventory_code=data["inventory_code"].strip(),
        serial_number=data["serial_number"].strip(),
        brand=data["brand"].strip(),
        model=data["model"].strip(),
        device_type=data["device_type"].strip(),
        risk_class=data.get("risk_class", "SOPORTE_VIDA"),
        acquisition_date=acq_date,
        replacement_cost=float(data["replacement_cost"]),
        preventive_interval_days=interval,
        last_service_date=date.today(),
        next_preventive_date=next_prev,
        current_state="OPERATIVO",
    )
    db.session.add(asset)
    db.session.commit()
    return jsonify({"asset": asset.to_dict()}), 201


@assets_bp.get("/symptoms")
@jwt_required()
def list_symptoms():
    device_type = request.args.get("device_type")
    query = SymptomCatalog.query
    if device_type:
        query = query.filter_by(device_type=device_type)
    symptoms = query.order_by(SymptomCatalog.default_severity, SymptomCatalog.id).all()
    return jsonify({"symptoms": [s.to_dict() for s in symptoms]})


@assets_bp.get("/preventive-due")
@jwt_required()
def list_preventive_due():
    user = get_current_user()
    days = request.args.get("days", default=15, type=int)
    limit_date = date.today() + timedelta(days=days)
    assets = (
        MedicalAsset.query.filter_by(hospital_id=user.hospital_id)
        .filter(MedicalAsset.current_state != "BAJA_DEFINITIVA")
        .filter(MedicalAsset.next_preventive_date <= limit_date)
        .order_by(MedicalAsset.next_preventive_date.asc())
        .all()
    )
    today = date.today()
    items = []
    for a in assets:
        d = a.to_dict()
        d["days_remaining"] = (a.next_preventive_date - today).days if a.next_preventive_date else -999
        items.append(d)
    return jsonify({"assets": items})


@assets_bp.post("/<int:asset_id>/preventive-start")
@roles_required("BIOMEDICO", "JEFE_TALLER")
def start_preventive(asset_id: int):
    user = get_current_user()
    asset = MedicalAsset.query.filter_by(id=asset_id, hospital_id=user.hospital_id).first_or_404()
    data = request.get_json(silent=True) or {}
    try:
        wo = start_preventive_maintenance(asset, user, notes=data.get("notes"))
        return jsonify({"work_order": wo.to_dict(), "asset": asset.to_dict()}), 201
    except StateTransitionError as exc:
        return jsonify({"error": exc.message}), exc.status_code


@assets_bp.post("/<int:asset_id>/inspect")
@roles_required("BIOMEDICO", "JEFE_TALLER")
def periodic_inspect(asset_id: int):
    user = get_current_user()
    asset = MedicalAsset.query.filter_by(id=asset_id, hospital_id=user.hospital_id).first_or_404()
    data = request.get_json(silent=True) or {}
    notes = (data.get("result_notes") or "Inspección de seguridad eléctrica y funcional aprobada.").strip()
    try:
        cert = record_periodic_inspection(asset, user, notes)
        return jsonify({"certification": cert.to_dict(), "asset": asset.to_dict()}), 201
    except StateTransitionError as exc:
        return jsonify({"error": exc.message}), exc.status_code
