from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.database import get_db
from app.models.blood_request import BloodRequest
from app.models.campaign import Campaign
from app.models.response import DonorResponse
from app.models.user import User
from app.models.volunteer_assignment import VolunteerAssignment
from app.api.routes.campaigns import campaign_payload

router = APIRouter(prefix="/api/coordinator", tags=["coordinator-reporting"])


def request_report(item: BloodRequest):
    return {
        "id": item.id,
        "request_code": item.request_code,
        "blood_group": item.blood_group,
        "city": item.city,
        "urgency": item.urgency,
        "status": item.status,
        "units_required": item.units_required,
        "units_confirmed": item.units_confirmed,
        "legacy_fulfillment_unverified": item.legacy_fulfillment_unverified,
        "escalation_status": item.escalation_status,
        "created_at": item.created_at,
        "fulfilled_at": item.fulfilled_at,
    }


def response_report(item: DonorResponse):
    return {"id": item.id, "request_id": item.request_id, "donor_id": item.donor_id, "response": item.response, "responded_at": item.responded_at}


def assignment_report(item: VolunteerAssignment):
    return {"id": item.id, "request_id": item.request_id, "volunteer_id": item.volunteer_id, "status": item.status, "assigned_at": item.assigned_at, "completed_at": item.completed_at}


@router.get("/analytics")
async def analytics(user: User = Depends(require_role(["coordinator"])), db: Session = Depends(get_db)):
    requests = db.query(BloodRequest).all()
    donors = db.query(User).filter(User.role == "donor").count()
    volunteers = db.query(User).filter(User.role == "volunteer").count()
    return {
        "requests": {
            "total": len(requests),
            "submitted": sum(item.status == "submitted" for item in requests),
            "verified": sum(item.status == "verified" for item in requests),
            "active": sum(item.status in {"submitted", "verified", "coordinating", "partially_fulfilled"} for item in requests),
            "fulfilled": sum(item.status == "fulfilled" and not item.legacy_fulfillment_unverified for item in requests),
            "legacy_fulfillment_unverified": sum(item.legacy_fulfillment_unverified for item in requests),
            "partially_fulfilled": sum(item.status == "partially_fulfilled" for item in requests),
            "urgent": sum(item.urgency in {"Urgent", "Emergency"} for item in requests),
        },
        "donors": {"registered": donors},
        "volunteers": {"total": volunteers},
        "assignments": {
            "total": db.query(VolunteerAssignment).count(),
            "assigned": db.query(VolunteerAssignment).filter(VolunteerAssignment.status == "assigned").count(),
            "active": db.query(VolunteerAssignment).filter(VolunteerAssignment.status.in_(["accepted", "in_progress"])).count(),
            "completed": db.query(VolunteerAssignment).filter(VolunteerAssignment.status == "completed").count(),
        },
        "campaigns": {
            "total": db.query(Campaign).count(),
            "published": db.query(Campaign).filter(Campaign.status == "published").count(),
            "completed": db.query(Campaign).filter(Campaign.status == "completed").count(),
        },
    }


@router.get("/reports")
async def reports(user: User = Depends(require_role(["coordinator"])), db: Session = Depends(get_db)):
    return {
        "recent_requests": [request_report(item) for item in db.query(BloodRequest).order_by(BloodRequest.created_at.desc()).limit(20).all()],
        "fulfilled_requests": [request_report(item) for item in db.query(BloodRequest).filter(BloodRequest.status == "fulfilled", BloodRequest.legacy_fulfillment_unverified.is_(False)).order_by(BloodRequest.fulfilled_at.desc()).limit(20).all()],
        "legacy_fulfillment_unverified": [request_report(item) for item in db.query(BloodRequest).filter(BloodRequest.legacy_fulfillment_unverified.is_(True)).order_by(BloodRequest.updated_at.desc()).limit(20).all()],
        "donor_responses": [response_report(item) for item in db.query(DonorResponse).order_by(DonorResponse.responded_at.desc()).limit(50).all()],
        "volunteer_activity": [assignment_report(item) for item in db.query(VolunteerAssignment).order_by(VolunteerAssignment.updated_at.desc()).limit(50).all()],
        "campaign_activity": [campaign_payload(item) for item in db.query(Campaign).order_by(Campaign.created_at.desc()).limit(50).all()],
    }