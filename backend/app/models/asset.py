from datetime import datetime, timezone
from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


ASSET_STATES = (
    "OPERATIVO",
    "REPORTADO",
    "BLOQUEADO",
    "EN_MANTENIMIENTO_PREVENTIVO",
    "EN_DIAGNOSTICO",
    "EN_ESPERA_REFACCION",
    "EN_CALIBRACION",
    "CERTIFICADO_PENDIENTE_RECEPCION",
    "BAJA_DEFINITIVA",
)


class MedicalAsset(db.Model):
    __tablename__ = "medical_assets"

    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"), nullable=False, index=True)
    area_id = db.Column(db.Integer, db.ForeignKey("clinical_areas.id"), nullable=False, index=True)
    inventory_code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    serial_number = db.Column(db.String(80), unique=True, nullable=False, index=True)
    brand = db.Column(db.String(80), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    device_type = db.Column(db.String(100), nullable=False, index=True)
    risk_class = db.Column(db.String(30), nullable=False, default="SOPORTE_VIDA")  # SOPORTE_VIDA | NO_CRITICO
    acquisition_date = db.Column(db.Date, nullable=False)
    replacement_cost = db.Column(db.Numeric(12, 2), nullable=False)
    preventive_interval_days = db.Column(db.Integer, nullable=False, default=180)
    last_service_date = db.Column(db.Date, nullable=True)
    next_preventive_date = db.Column(db.Date, nullable=True)
    current_state = db.Column(db.String(40), nullable=False, default="OPERATIVO", index=True)
    has_critical_flag = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    area = db.relationship("ClinicalArea", back_populates="assets", lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "hospital_id": self.hospital_id,
            "area_id": self.area_id,
            "area_name": self.area.name if self.area else None,
            "area_code": self.area.area_code if self.area else None,
            "inventory_code": self.inventory_code,
            "serial_number": self.serial_number,
            "brand": self.brand,
            "model": self.model,
            "device_type": self.device_type,
            "risk_class": self.risk_class,
            "acquisition_date": self.acquisition_date.isoformat() if self.acquisition_date else None,
            "replacement_cost": float(self.replacement_cost),
            "preventive_interval_days": self.preventive_interval_days,
            "last_service_date": self.last_service_date.isoformat() if self.last_service_date else None,
            "next_preventive_date": self.next_preventive_date.isoformat() if self.next_preventive_date else None,
            "current_state": self.current_state,
            "has_critical_flag": self.has_critical_flag,
        }


class SymptomCatalog(db.Model):
    __tablename__ = "symptom_catalog"

    id = db.Column(db.Integer, primary_key=True)
    device_type = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.String(200), nullable=False)
    default_severity = db.Column(db.String(20), nullable=False)  # CRITICA | MEDIA | BAJA
    category = db.Column(db.String(50), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "device_type": self.device_type,
            "description": self.description,
            "default_severity": self.default_severity,
            "category": self.category,
        }
