from datetime import datetime, timezone
from app.models import Certification


def generate_unique_folio(year: int | None = None) -> str:
    """Generate unique institutional BioTrack folio: CAL-YYYY-XXXXX (SDS Section 1.2 #5)."""
    target_year = year or datetime.now(timezone.utc).year
    prefix = f"CAL-{target_year}-"
    last_cert = (
        Certification.query.filter(Certification.folio_biotrack.like(f"{prefix}%"))
        .order_by(Certification.folio_biotrack.desc())
        .with_for_update()
        .first()
    )
    next_seq = 1
    if last_cert:
        try:
            next_seq = int(last_cert.folio_biotrack.split("-")[-1]) + 1
        except (ValueError, IndexError):
            next_seq = 1
    return f"{prefix}{next_seq:05d}"
