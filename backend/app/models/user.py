from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


ROLES = (
    "CLINICO",
    "BIOMEDICO",
    "JEFE_TALLER",
    "RESPONSABLE_AREA",
    "DIRECCION",
    "AUDITOR",
)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"), nullable=False, index=True)
    area_id = db.Column(db.Integer, db.ForeignKey("clinical_areas.id"), nullable=True)
    directory_uid = db.Column(db.String(80), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(40), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    area = db.relationship("ClinicalArea", lazy="joined")

    def set_password(self, raw_password: str):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    def to_dict(self):
        return {
            "id": self.id,
            "hospital_id": self.hospital_id,
            "area_id": self.area_id,
            "area_name": self.area.name if self.area else None,
            "directory_uid": self.directory_uid,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "role": self.role,
            "is_active": self.is_active,
        }


class OnCallRoster(db.Model):
    __tablename__ = "on_call_rosters"

    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"), nullable=False, index=True)
    biomedical_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    coverage_areas_json = db.Column(db.JSON, nullable=False, default=list)  # list of area_ids (empty = all)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    contact_phone = db.Column(db.String(40), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    biomedical_user = db.relationship("User", lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "hospital_id": self.hospital_id,
            "biomedical_user_id": self.biomedical_user_id,
            "biomedical_name": self.biomedical_user.full_name if self.biomedical_user else None,
            "biomedical_role": self.biomedical_user.role if self.biomedical_user else None,
            "coverage_areas": self.coverage_areas_json or [],
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "contact_phone": self.contact_phone,
            "is_active": self.is_active,
        }
