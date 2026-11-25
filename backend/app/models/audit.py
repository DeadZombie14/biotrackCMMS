from datetime import datetime, timezone
from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuditEvent(db.Model):
    """Append-only immutable audit log with per-asset SHA-256 hash chaining (AD-02, QA-03)."""

    __tablename__ = "audit_events"

    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("medical_assets.id"), nullable=False, index=True)
    event_type = db.Column(db.String(60), nullable=False, index=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    timestamp_utc = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    payload_json = db.Column(db.Text, nullable=False)
    prev_hash = db.Column(db.String(64), nullable=False)
    record_hash = db.Column(db.String(64), nullable=False, unique=True)

    actor = db.relationship("User", lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "hospital_id": self.hospital_id,
            "asset_id": self.asset_id,
            "event_type": self.event_type,
            "actor_user_id": self.actor_user_id,
            "actor_name": self.actor.full_name if self.actor else None,
            "actor_role": self.actor.role if self.actor else None,
            "timestamp_utc": self.timestamp_utc.isoformat() if self.timestamp_utc else None,
            "payload_json": self.payload_json,
            "prev_hash": self.prev_hash,
            "record_hash": self.record_hash,
        }
