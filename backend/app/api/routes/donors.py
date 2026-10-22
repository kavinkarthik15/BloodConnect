from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_role
from app.db.database import get_db
from app.models.donor import DonorProfile
from app.models.match import DonorMatch
from app.models.response import DonorResponse
from app.models.blood_request import BloodRequest
from app.models.user import User
from app.schemas.donor import DonorProfileCreate, DonorProfileResponse, DonorProfileUpdate
from app.services.audit_service import record_audit
from app.services.donor_service import create_or_update_donor_profile, get_donor_profile, set_donor_availability

router = APIRouter(prefix="/api/donors", tags=["donors"])


def _safe_match_payload(match: DonorMatch, request: BloodRequest, response: DonorResponse | None):
    return {
        "match_id": match.id,
        "request_id": request.id,
        "request_code": request.request_code,
        "blood_group_required": request.blood_group,
        "units_required": request.units_required,
        "units_confirmed": request.units_confirmed,
        "legacy_fulfillment_unverified": request.legacy_fulfillment_unverified,
        "hospital_name": request.hospital_name,
        "city": request.city,
        "urgency": request.urgency,
        "required_at": request.required_at,
        "request_latitude": request.latitude,
        "request_longitude": request.longitude,
        "request_status": request.status,
        "escalation_status": request.escalation_status,
        "distance_km": match.distance_km,
        "match_score": match.match_score,
        "donor_response_status": response.response if response else "pending",
        "response_timestamp": response.responded_at if response else None,
    }


@router.get("/me", response_model=DonorProfileResponse | None)
async def get_my_profile(user: User = Depends(require_role(["donor", "coordinator"])) , db: Session = Depends(get_db)):
    profile = get_donor_profile(db, user.id)
    return profile


@router.post("/me", response_model=DonorProfileResponse)
async def create_my_profile(payload: DonorProfileCreate, user: User = Depends(require_role(["donor", "coordinator"])), db: Session = Depends(get_db)):
    profile = create_or_update_donor_profile(db, user.id, payload)
    return profile


@router.put("/me", response_model=DonorProfileResponse)
async def update_my_profile(payload: DonorProfileUpdate, user: User = Depends(require_role(["donor", "coordinator"])), db: Session = Depends(get_db)):
    profile = create_or_update_donor_profile(db, user.id, payload)
    return profile


@router.patch("/me/availability")
async def update_availability(available: bool, user: User = Depends(require_role(["donor", "coordinator"])), db: Session = Depends(get_db)):
    donor = set_donor_availability(db, user.id, available)
    return {"available": donor.available}


@router.get("/me/matches")
async def get_my_matches(user: User = Depends(require_role(["donor"])), db: Session = Depends(get_db)):
    matches = db.query(DonorMatch).filter(DonorMatch.donor_id == user.id).order_by(DonorMatch.created_at.desc()).all()
    result = []
    for match in matches:
        request = db.query(BloodRequest).filter(BloodRequest.id == match.request_id).first()
        if not request:
            continue
        response = db.query(DonorResponse).filter(
            DonorResponse.request_id == request.id,
            DonorResponse.donor_id == user.id,
        ).first()
        result.append(_safe_match_payload(match, request, response))
    return result


@router.get("/me/matches/{request_id}")
async def get_my_match_detail(request_id: int, user: User = Depends(require_role(["donor"])), db: Session = Depends(get_db)):
    match = db.query(DonorMatch).filter(DonorMatch.request_id == request_id, DonorMatch.donor_id == user.id).first()
    if not match:
        raise HTTPException(status_code=403, detail="You are not matched to this request.")
    request = db.query(BloodRequest).filter(BloodRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    response = db.query(DonorResponse).filter(
        DonorResponse.request_id == request_id,
        DonorResponse.donor_id == user.id,
    ).first()
    return _safe_match_payload(match, request, response)


@router.get("/me/accepted")
async def get_my_accepted(user: User = Depends(require_role(["donor"])), db: Session = Depends(get_db)):
    responses = db.query(DonorResponse).filter(
        DonorResponse.donor_id == user.id,
        DonorResponse.response == "accepted",
    ).order_by(DonorResponse.responded_at.desc()).all()
    return _response_payloads(db, user.id, responses)


@router.get("/me/history")
async def get_my_history(user: User = Depends(require_role(["donor"])), db: Session = Depends(get_db)):
    responses = db.query(DonorResponse).filter(
        DonorResponse.donor_id == user.id,
    ).order_by(DonorResponse.responded_at.desc()).all()
    return _response_payloads(db, user.id, responses)


def _response_payloads(db: Session, donor_id: int, responses: list[DonorResponse]):
    result = []
    for response in responses:
        request = db.query(BloodRequest).filter(BloodRequest.id == response.request_id).first()
        if not request:
            continue
        result.append({
            "request_id": request.id,
            "request_code": request.request_code,
            "blood_group": request.blood_group,
            "hospital_name": request.hospital_name,
            "city": request.city,
            "urgency": request.urgency,
            "response": response.response,
            "response_timestamp": response.responded_at,
            "request_status": request.status,
            "units_required": request.units_required,
            "units_confirmed": request.units_confirmed,
            "escalation_status": request.escalation_status,
        })
    return result


@router.get("/management")
async def list_donors_for_coordinator(
    search: str | None = None,
    blood_group: str | None = None,
    city: str | None = None,
    available: bool | None = None,
    verified: bool | None = None,
    user: User = Depends(require_role(["coordinator"])),
    db: Session = Depends(get_db),
):
    query = db.query(DonorProfile, User).join(User, User.id == DonorProfile.user_id)
    if blood_group:
        query = query.filter(DonorProfile.blood_group == blood_group)
    if city:
        query = query.filter(DonorProfile.city.ilike(f"%{city}%"))
    if available is not None:
        query = query.filter(DonorProfile.available.is_(available))
    if verified is not None:
        query = query.filter(DonorProfile.verified.is_(verified))
    if search:
        term = f"%{search}%"
        query = query.filter((User.full_name.ilike(term)) | DonorProfile.city.ilike(term) | DonorProfile.area.ilike(term))
    return [
        {
            "donor_id": donor.user_id,
            "name": donor_user.full_name,
            "blood_group": donor.blood_group,
            "city": donor.city,
            "area": donor.area,
            "available": donor.available,
            "verified": donor.verified,
            "updated_at": donor.updated_at,
        }
        for donor, donor_user in query.order_by(User.full_name.asc()).all()
    ]


@router.patch("/management/{donor_id}/verification")
async def update_donor_verification(
    donor_id: int,
    verified: bool,
    user: User = Depends(require_role(["coordinator"])),
    db: Session = Depends(get_db),
):
    donor = db.query(DonorProfile).filter(DonorProfile.user_id == donor_id).first()
    if not donor:
        raise HTTPException(status_code=404, detail="Donor profile not found.")
    donor.verified = verified
    db.commit()
    db.refresh(donor)
    record_audit(db, user.id, "donor_verification_updated", "donor_profile", donor_id, {"verified": donor.verified, "user_id": donor_id})
    return {"donor_id": donor_id, "verified": donor.verified}


@router.get("/management/volunteers")
async def list_volunteers_for_coordinator(user: User = Depends(require_role(["coordinator"])), db: Session = Depends(get_db)):
    volunteers = db.query(User).filter(User.role == "volunteer").order_by(User.full_name.asc()).all()
    return [
        {
            "volunteer_id": volunteer.id,
            "name": volunteer.full_name,
            "active": volunteer.active,
            "city": volunteer.college_org,
            "area": volunteer.nss_unit,
        }
        for volunteer in volunteers
    ]
