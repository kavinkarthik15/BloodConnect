from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_role
from app.db.database import get_db
from app.models.blood_request import BloodRequest
from app.models.notification import Notification
from app.models.user import User
from app.models.volunteer_assignment import VolunteerAssignment
from app.services.audit_service import record_audit

router = APIRouter(prefix="/api/volunteers", tags=["volunteers"])

VALID_STATUSES = {"assigned", "accepted", "in_progress", "completed", "cancelled"}
NEXT_STATUS = {
    "assigned": {"accepted", "cancelled"},
    "accepted": {"in_progress", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


class AssignmentCreate(BaseModel):
    volunteer_id: int
    notes: str | None = None


def assignment_payload(db: Session, assignment: VolunteerAssignment):
    request = db.query(BloodRequest).filter(BloodRequest.id == assignment.request_id).first()
    volunteer = db.query(User).filter(User.id == assignment.volunteer_id).first()
    return {
        "id": assignment.id,
        "request_id": assignment.request_id,
        "request_code": request.request_code if request else None,
        "patient_reference": request.patient_reference if request else None,
        "blood_group": request.blood_group if request else None,
        "units_required": request.units_required if request else None,
        "hospital_name": request.hospital_name if request else None,
        "hospital_address": request.hospital_address if request else None,
        "city": request.city if request else None,
        "required_at": request.required_at if request else None,
        "urgency": request.urgency if request else None,
        "request_status": request.status if request else None,
        "volunteer_id": assignment.volunteer_id,
        "volunteer_name": volunteer.full_name if volunteer else None,
        "status": assignment.status,
        "notes": assignment.notes,
        "assigned_at": assignment.assigned_at,
        "accepted_at": assignment.accepted_at,
        "started_at": assignment.started_at,
        "completed_at": assignment.completed_at,
        "cancelled_at": assignment.cancelled_at,
    }


@router.post("/requests/{request_id}/assignments", status_code=201)
async def create_assignment(request_id: int, payload: AssignmentCreate, user: User = Depends(require_role(["coordinator"])), db: Session = Depends(get_db)):
    request = db.query(BloodRequest).filter(BloodRequest.id == request_id).first()
    volunteer = db.query(User).filter(User.id == payload.volunteer_id, User.role == "volunteer", User.active.is_(True)).first()
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    if not volunteer:
        raise HTTPException(status_code=404, detail="Active volunteer not found.")
    existing = db.query(VolunteerAssignment).filter(
        VolunteerAssignment.request_id == request_id,
        VolunteerAssignment.volunteer_id == payload.volunteer_id,
        VolunteerAssignment.status.notin_(["completed", "cancelled"]),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="An active assignment already exists for this volunteer and request.")
    assignment = VolunteerAssignment(request_id=request_id, volunteer_id=payload.volunteer_id, assigned_by=user.id, notes=payload.notes)
    db.add(assignment)
    db.flush()
    db.add(Notification(
        user_id=payload.volunteer_id,
        type="volunteer_assigned",
        title="Volunteer assignment received",
        message=f"You have been assigned to coordinate request {request.request_code}.",
        related_entity_id=request_id,
    ))
    db.commit()
    db.refresh(assignment)
    record_audit(db, user.id, "volunteer_assigned", "volunteer_assignment", assignment.id, {"request_id": request_id, "volunteer_id": payload.volunteer_id})
    return assignment_payload(db, assignment)


@router.get("/requests/{request_id}/assignments")
async def list_request_assignments(request_id: int, user: User = Depends(require_role(["coordinator"])), db: Session = Depends(get_db)):
    return [assignment_payload(db, item) for item in db.query(VolunteerAssignment).filter(VolunteerAssignment.request_id == request_id).order_by(VolunteerAssignment.created_at.desc()).all()]


@router.get("/me/assignments")
async def list_my_assignments(user: User = Depends(require_role(["volunteer"])), db: Session = Depends(get_db)):
    assignments = db.query(VolunteerAssignment).filter(VolunteerAssignment.volunteer_id == user.id).order_by(VolunteerAssignment.created_at.desc()).all()
    return [assignment_payload(db, item) for item in assignments]


@router.get("/me/assignments/{assignment_id}")
async def get_my_assignment(assignment_id: int, user: User = Depends(require_role(["volunteer"])), db: Session = Depends(get_db)):
    assignment = db.query(VolunteerAssignment).filter(VolunteerAssignment.id == assignment_id, VolunteerAssignment.volunteer_id == user.id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    return assignment_payload(db, assignment)


@router.patch("/me/assignments/{assignment_id}/status")
async def update_my_assignment(assignment_id: int, status: str, user: User = Depends(require_role(["volunteer"])), db: Session = Depends(get_db)):
    if status not in VALID_STATUSES or status == "cancelled":
        raise HTTPException(status_code=422, detail="Invalid volunteer assignment status.")
    assignment = db.query(VolunteerAssignment).filter(VolunteerAssignment.id == assignment_id, VolunteerAssignment.volunteer_id == user.id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    if status not in NEXT_STATUS[assignment.status]:
        raise HTTPException(status_code=409, detail=f"Cannot move assignment from {assignment.status} to {status}.")
    assignment.status = status
    now = datetime.utcnow()
    if status == "accepted":
        assignment.accepted_at = now
    elif status == "in_progress":
        assignment.started_at = now
    elif status == "completed":
        assignment.completed_at = now
    db.commit()
    db.refresh(assignment)
    record_audit(db, user.id, "assignment_status_changed", "volunteer_assignment", assignment.id, {"from_status": assignment.status, "to_status": status})
    return assignment_payload(db, assignment)


@router.patch("/{assignment_id}/cancel")
async def cancel_assignment(assignment_id: int, user: User = Depends(require_role(["coordinator"])), db: Session = Depends(get_db)):
    assignment = db.query(VolunteerAssignment).filter(VolunteerAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    if "cancelled" not in NEXT_STATUS[assignment.status]:
        raise HTTPException(status_code=409, detail=f"Cannot cancel assignment from {assignment.status}.")
    assignment.status = "cancelled"
    assignment.cancelled_at = datetime.utcnow()
    db.add(Notification(user_id=assignment.volunteer_id, type="volunteer_assignment_cancelled", title="Volunteer assignment cancelled", message="A volunteer assignment was cancelled by the coordinator.", related_entity_id=assignment.request_id))
    db.commit()
    db.refresh(assignment)
    record_audit(db, user.id, "assignment_cancelled", "volunteer_assignment", assignment.id, {"request_id": assignment.request_id})
    return assignment_payload(db, assignment)