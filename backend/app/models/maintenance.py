from datetime import datetime, timezone
from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class IncidentReport(db.Model):
    __tablename__ = "incident_reports"

    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("medical_assets.id"), nullable=False, index=True)
    event_type = db.Column(db.String(40), nullable=False, default="FALLA_CORRECTIVA")
    # FALLA_CORRECTIVA | PREVENTIVO_PROGRAMADO | INSPECCION_PERIODICA
    severity = db.Column(db.String(20), nullable=False, default="MEDIA")  # CRITICA | MEDIA | BAJA
    symptom_id = db.Column(db.Integer, db.ForeignKey("symptom_catalog.id"), nullable=True)
    symptom_text = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    reported_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    terminal_ip = db.Column(db.String(64), nullable=True)
    is_deferred = db.Column(db.Boolean, nullable=False, default=False)
    declared_occurred_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    asset = db.relationship("MedicalAsset", lazy="joined")
    reported_by = db.relationship("User", foreign_keys=[reported_by_id], lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "hospital_id": self.hospital_id,
            "asset_id": self.asset_id,
            "asset_inventory_code": self.asset.inventory_code if self.asset else None,
            "asset_serial": self.asset.serial_number if self.asset else None,
            "asset_type": self.asset.device_type if self.asset else None,
            "area_name": self.asset.area.name if self.asset and self.asset.area else None,
            "event_type": self.event_type,
            "severity": self.severity,
            "symptom_id": self.symptom_id,
            "symptom_text": self.symptom_text,
            "notes": self.notes,
            "reported_by_id": self.reported_by_id,
            "reported_by_name": self.reported_by.full_name if self.reported_by else None,
            "terminal_ip": self.terminal_ip,
            "is_deferred": self.is_deferred,
            "declared_occurred_at": self.declared_occurred_at.isoformat() if self.declared_occurred_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class WorkOrder(db.Model):
    __tablename__ = "work_orders"

    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"), nullable=False, index=True)
    incident_report_id = db.Column(db.Integer, db.ForeignKey("incident_reports.id"), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("medical_assets.id"), nullable=False, index=True)
    biomedical_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    service_type = db.Column(db.String(30), nullable=False, default="CORRECTIVO")
    # CORRECTIVO | PREVENTIVO | INSPECCION
    technical_diagnosis = db.Column(db.Text, nullable=True)
    parts_used = db.Column(db.Text, nullable=True)
    parts_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0.0)
    started_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    closed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(40), nullable=False, default="ABIERTA", index=True)
    # ABIERTA | EN_DIAGNOSTICO | ESPERA_REFACCION | EN_CALIBRACION | CERTIFICADA | CERRADA | BAJA_DEFINITIVA

    incident = db.relationship("IncidentReport", lazy="joined")
    asset = db.relationship("MedicalAsset", lazy="joined")
    biomedical_user = db.relationship("User", foreign_keys=[biomedical_user_id], lazy="joined")
    certification = db.relationship("Certification", back_populates="work_order", uselist=False, lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "hospital_id": self.hospital_id,
            "incident_report_id": self.incident_report_id,
            "asset_id": self.asset_id,
            "asset": self.asset.to_dict() if self.asset else None,
            "incident": self.incident.to_dict() if self.incident else None,
            "biomedical_user_id": self.biomedical_user_id,
            "biomedical_name": self.biomedical_user.full_name if self.biomedical_user else None,
            "service_type": self.service_type,
            "technical_diagnosis": self.technical_diagnosis,
            "parts_used": self.parts_used,
            "parts_cost": float(self.parts_cost or 0),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "status": self.status,
            "certification": self.certification.to_dict() if self.certification else None,
        }


class Certification(db.Model):
    __tablename__ = "certifications"

    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"), nullable=False, index=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey("work_orders.id"), nullable=False, unique=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("medical_assets.id"), nullable=False, index=True)
    folio_biotrack = db.Column(db.String(30), unique=True, nullable=False, index=True)
    external_lab_folio = db.Column(db.String(80), nullable=True)
    external_cert_note = db.Column(db.String(255), nullable=True)
    metrological_result = db.Column(db.Text, nullable=False)
    service_date = db.Column(db.Date, nullable=False)
    expiration_date = db.Column(db.Date, nullable=False)

    # Firma 1: Ingeniero Biomédico
    biomedical_signer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    biomedical_signed_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    biomedical_signature_hash = db.Column(db.String(64), nullable=False)

    # Firma 2: Responsable del Área Clínica
    area_receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    area_received_at = db.Column(db.DateTime, nullable=True)
    area_signature_hash = db.Column(db.String(64), nullable=True)

    public_qr_token = db.Column(db.String(64), unique=True, nullable=False, index=True)

    work_order = db.relationship("WorkOrder", back_populates="certification")
    asset = db.relationship("MedicalAsset", lazy="joined")
    biomedical_signer = db.relationship("User", foreign_keys=[biomedical_signer_id], lazy="joined")
    area_receiver = db.relationship("User", foreign_keys=[area_receiver_id], lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "work_order_id": self.work_order_id,
            "asset_id": self.asset_id,
            "folio_biotrack": self.folio_biotrack,
            "external_lab_folio": self.external_lab_folio,
            "external_cert_note": self.external_cert_note,
            "metrological_result": self.metrological_result,
            "service_date": self.service_date.isoformat() if self.service_date else None,
            "expiration_date": self.expiration_date.isoformat() if self.expiration_date else None,
            "biomedical_signer_id": self.biomedical_signer_id,
            "biomedical_signer_name": self.biomedical_signer.full_name if self.biomedical_signer else None,
            "biomedical_signed_at": self.biomedical_signed_at.isoformat() if self.biomedical_signed_at else None,
            "biomedical_signature_hash": self.biomedical_signature_hash,
            "area_receiver_id": self.area_receiver_id,
            "area_receiver_name": self.area_receiver.full_name if self.area_receiver else None,
            "area_received_at": self.area_received_at.isoformat() if self.area_received_at else None,
            "area_signature_hash": self.area_signature_hash,
            "public_qr_token": self.public_qr_token,
            "is_double_signed": bool(self.biomedical_signature_hash and self.area_signature_hash),
        }
