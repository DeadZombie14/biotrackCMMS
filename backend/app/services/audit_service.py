import hashlib
import json
from datetime import datetime, timezone
from sqlalchemy import text
from app.extensions import db
from app.models import AuditEvent

GENESIS_HASH = "0" * 64


def _canonical_timestamp(dt: datetime) -> str:
    # Truncate to whole seconds so MariaDB DATETIME(0) round-trips identically
    clean = dt.replace(microsecond=0)
    return clean.strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_record_hash(
    hospital_id: int,
    asset_id: int,
    event_type: str,
    actor_user_id: int,
    timestamp_utc: datetime,
    payload_json: str,
    prev_hash: str,
) -> str:
    raw = "|".join(
        [
            str(hospital_id),
            str(asset_id),
            str(event_type),
            str(actor_user_id),
            _canonical_timestamp(timestamp_utc),
            payload_json,
            prev_hash,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def record_audit_event(
    *,
    hospital_id: int,
    asset_id: int,
    event_type: str,
    actor_user_id: int,
    payload: dict,
    timestamp_utc: datetime | None = None,
) -> AuditEvent:
    """Append an immutable SHA-256 chained audit event within the active DB transaction."""
    ts = (timestamp_utc or datetime.now(timezone.utc).replace(tzinfo=None)).replace(
        microsecond=0
    )
    last_event = (
        AuditEvent.query.filter_by(asset_id=asset_id)
        .order_by(AuditEvent.id.desc())
        .with_for_update()
        .first()
    )
    prev_hash = last_event.record_hash if last_event else GENESIS_HASH
    payload_str = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    record_hash = compute_record_hash(
        hospital_id=hospital_id,
        asset_id=asset_id,
        event_type=event_type,
        actor_user_id=actor_user_id,
        timestamp_utc=ts,
        payload_json=payload_str,
        prev_hash=prev_hash,
    )
    event = AuditEvent(
        hospital_id=hospital_id,
        asset_id=asset_id,
        event_type=event_type,
        actor_user_id=actor_user_id,
        timestamp_utc=ts,
        payload_json=payload_str,
        prev_hash=prev_hash,
        record_hash=record_hash,
    )
    db.session.add(event)
    db.session.flush()
    return event


def verify_asset_audit_chain(asset_id: int) -> dict:
    """Cryptographically verify the complete SHA-256 chain for an asset (QA-03, QA-05)."""
    events = (
        AuditEvent.query.filter_by(asset_id=asset_id)
        .order_by(AuditEvent.id.asc())
        .all()
    )
    expected_prev = GENESIS_HASH
    for idx, ev in enumerate(events):
        if ev.prev_hash != expected_prev:
            return {
                "valid": False,
                "total_events": len(events),
                "broken_at_index": idx,
                "broken_event_id": ev.id,
                "reason": "Encadenamiento prev_hash roto (posible borrado o inserción fraudulenta).",
            }
        recomputed = compute_record_hash(
            hospital_id=ev.hospital_id,
            asset_id=ev.asset_id,
            event_type=ev.event_type,
            actor_user_id=ev.actor_user_id,
            timestamp_utc=ev.timestamp_utc,
            payload_json=ev.payload_json,
            prev_hash=ev.prev_hash,
        )
        if recomputed != ev.record_hash:
            return {
                "valid": False,
                "total_events": len(events),
                "broken_at_index": idx,
                "broken_event_id": ev.id,
                "reason": "Huella SHA-256 inválida (posible alteración directa en base de datos).",
            }
        expected_prev = ev.record_hash

    return {
        "valid": True,
        "total_events": len(events),
        "head_hash": expected_prev if events else GENESIS_HASH,
        "reason": "Cadena íntegra: todos los registros coinciden criptográficamente (SHA-256).",
    }


def install_mariadb_immutability_triggers():
    """Install MariaDB BEFORE UPDATE / BEFORE DELETE triggers on audit_events (QA-03)."""
    db.session.execute(text("DROP TRIGGER IF EXISTS trg_audit_events_no_update"))
    db.session.execute(text("DROP TRIGGER IF EXISTS trg_audit_events_no_delete"))
    db.session.execute(
        text(
            """
            CREATE TRIGGER trg_audit_events_no_update
            BEFORE UPDATE ON audit_events
            FOR EACH ROW
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'BioTrack Audit Trail is immutable: UPDATE forbidden (NOM-151 / QA-03).'
            """
        )
    )
    db.session.execute(
        text(
            """
            CREATE TRIGGER trg_audit_events_no_delete
            BEFORE DELETE ON audit_events
            FOR EACH ROW
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'BioTrack Audit Trail is immutable: DELETE forbidden (NOM-151 / QA-03).'
            """
        )
    )
    db.session.commit()
