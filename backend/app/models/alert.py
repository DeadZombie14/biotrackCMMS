from datetime import datetime, timezone
from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DispatchAlert(db.Model):
    """Active dispatch alerts to on-call biomedical engineers with escalation tracking (AD-05, QA-07)."""

    __tablename__ = "dispatch_alerts"

    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"), nullable=False, index=True)
    incident_report_id = db.Column(db.Integer, db.ForeignKey("incident_reports.id"), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("medical_assets.id"), nullable=False, index=True)
    assigned_biomedical_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    escalated_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="PENDIENTE", index=True)
    # PENDIENTE | ACUSADO | ESCALADO | RESUELTO
    channel = db.Column(db.String(40), nullable=False, default="CONSOLA+MENSAJE_DIRECTO")
    message_body = db.Column(db.Text, nullable=False)
    dispatched_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    ack_deadline_at = db.Column(db.DateTime, nullable=False)
    acknowledged_at = db.Column(db.DateTime, nullable=True)
    escalated_at = db.Column(db.DateTime, nullable=True)

    asset = db.relationship("MedicalAsset", lazy="joined")
    assigned_biomedical = db.relationship("User", foreign_keys=[assigned_biomedical_id], lazy="joined")
    escalated_to = db.relationship("User", foreign_keys=[escalated_to_id], lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "hospital_id": self.hospital_id,
            "incident_report_id": self.incident_report_id,
            "asset_id": self.asset_id,
            "asset_inventory_code": self.asset.inventory_code if self.asset else None,
            "asset_type": self.asset.device_type if self.asset else None,
            "area_name": self.asset.area.name if self.asset and self.asset.area else None,
            "assigned_biomedical_id": self.assigned_biomedical_id,
            "assigned_biomedical_name": self.assigned_biomedical.full_name if self.assigned_biomedical else None,
            "assigned_phone": self.assigned_biomedical.phone if self.assigned_biomedical else None,
            "escalated_to_id": self.escalated_to_id,
            "escalated_to_name": self.escalated_to.full_name if self.escalated_to else None,
            "status": self.status,
            "channel": self.channel,
            "message_body": self.message_body,
            "dispatched_at": self.dispatched_at.isoformat() if self.dispatched_at else None,
            "ack_deadline_at": self.ack_deadline_at.isoformat() if self.ack_deadline_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "escalated_at": self.escalated_at.isoformat() if self.escalated_at else None,
        }
