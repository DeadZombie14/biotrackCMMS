from datetime import datetime, timezone
from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Hospital(db.Model):
    __tablename__ = "hospitals"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    municipality = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    unit_type = db.Column(db.String(80), nullable=False, default="Hospital General")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    areas = db.relationship("ClinicalArea", back_populates="hospital", lazy="select")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "municipality": self.municipality,
            "address": self.address,
            "unit_type": self.unit_type,
        }


class ClinicalArea(db.Model):
    __tablename__ = "clinical_areas"

    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    area_code = db.Column(db.String(30), nullable=False)
    criticality_level = db.Column(db.String(20), nullable=False, default="ALTA")  # CRITICA | ALTA | MEDIA
    terminal_identifier = db.Column(db.String(60), nullable=True, unique=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    hospital = db.relationship("Hospital", back_populates="areas")
    assets = db.relationship("MedicalAsset", back_populates="area", lazy="select")

    def to_dict(self):
        return {
            "id": self.id,
            "hospital_id": self.hospital_id,
            "name": self.name,
            "area_code": self.area_code,
            "criticality_level": self.criticality_level,
            "terminal_identifier": self.terminal_identifier,
        }
