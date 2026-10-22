from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.blood_request import BloodRequest
from app.models.notification import Notification
from app.services.audit_service import record_audit


OPEN_REQUEST_STATUSES = {"submitted", "verified", "coordinating", "partially_fulfilled"}


def expire_due_requests(
    db: Session,
    now: datetime | None = None,
    request_id: int | None = None,
    actor_user_id: int | None = None,
) -> int:
    cutoff = now or datetime.now(timezone.utc)
    query = db.query(BloodRequest).filter(
        BloodRequest.status.in_(OPEN_REQUEST_STATUSES),
        BloodRequest.required_at <= cutoff,
    )
    if request_id is not None:
        query = query.filter(BloodRequest.id == request_id)
    requests = query.with_for_update().all()
    for request in requests:
        request.status = "expired"
        request.escalation_status = "emergency_overdue" if request.urgency.casefold() == "emergency" else "overdue"
        record_audit(db, actor_user_id, "request_expired", "blood_request", request.id, {
            "request_code": request.request_code,
            "units_confirmed": request.units_confirmed,
        })
        db.add(Notification(
            user_id=request.requester_id,
            type="request_expired",
            title="Blood request deadline passed",
            message=f"Request {request.request_code} reached its required time and is no longer accepting responses.",
            related_entity_id=request.id,
        ))
    db.commit()
    return len(requests)
