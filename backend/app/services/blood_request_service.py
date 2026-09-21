from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.blood_request import BloodRequest
from app.models.notification import Notification
from app.models.user import User


def generate_request_code():
    return f"BCR-{datetime.utcnow().strftime('%Y')}-{str(uuid4().int)[:6].zfill(6)}"


def create_blood_request(db: Session, user_id: int, payload: dict):
    request = BloodRequest(
        request_code=generate_request_code(),
        requester_id=user_id,
        patient_reference=payload["patient_reference"],
        blood_group=payload["blood_group"],
        units_required=payload["units_required"],
        hospital_name=payload["hospital_name"],
        hospital_address=payload["hospital_address"],
        city=payload["city"],
        latitude=payload.get("latitude"),
        longitude=payload.get("longitude"),
        required_at=payload["required_at"],
        urgency=payload.get("urgency", "Normal"),
        contact_name=payload["contact_name"],
        contact_phone=payload["contact_phone"],
        notes=payload.get("notes"),
        status="submitted",
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    # notify coordinator of new request
    db.add(Notification(user_id=1, type="new_blood_request", title="New blood request", message=f"A new blood request {request.request_code} is awaiting verification.", related_entity_id=request.id))
    db.commit()
    return request


def get_request_by_id(db: Session, request_id: int):
    return db.query(BloodRequest).filter(BloodRequest.id == request_id).first()


def list_requests_for_user(db: Session, user_id: int):
    return db.query(BloodRequest).filter(BloodRequest.requester_id == user_id).order_by(BloodRequest.created_at.desc()).all()


def update_request_status(db: Session, request_id: int, status_value: str, verified_by: int | None = None):
    request = get_request_by_id(db, request_id)
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blood request not found.")
    request.status = status_value
    if status_value == "verified" and verified_by is not None:
        request.verified_by = verified_by
        request.verified_at = datetime.utcnow()
    if status_value == "fulfilled":
        request.fulfilled_at = datetime.utcnow()
    db.commit()
    db.refresh(request)
    return request


def ensure_request_access(db: Session, user: User, request_id: int):
    request = get_request_by_id(db, request_id)
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blood request not found.")
    if user.role == "coordinator":
        return request
    if request.requester_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to access this request.")
    return request
