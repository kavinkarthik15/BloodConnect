import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record_audit(
    db: Session,
    actor_user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: str | int | None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
):
    safe_metadata = dict(metadata or {})
    safe_metadata = {key: value for key, value in safe_metadata.items() if value is not None}

    audit = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        metadata_json=json.dumps(safe_metadata, default=str),
        ip_address=ip_address,
    )
    db.add(audit)
    db.flush()
    return audit
