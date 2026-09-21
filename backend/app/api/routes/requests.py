from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_role
from app.db.database import get_db
from app.models.blood_request import BloodRequest
from app.models.donor import DonorProfile
from app.models.match import DonorMatch
from app.models.notification import Notification
from app.models.response import DonorResponse
from app.models.user import User
from app.schemas.blood_request import BloodRequestCreate, BloodRequestResponse, BloodRequestUpdate
from app.services.audit_service import record_audit
from app.services.blood_request_service import create_blood_request, ensure_request_access, get_request_by_id, list_requests_for_user, update_request_status
from app.services.geocoding_service import resolve_coordinates
from app.services.matching_service import find_potential_matches
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/requests", tags=["requests"])


@router.post("", response_model=BloodRequestResponse)
async def create_request(payload: BloodRequestCreate, user: User = Depends(require_role(["requester", "coordinator"])), db: Session = Depends(get_db)):
    request_payload = payload.model_dump()
    if request_payload["latitude"] is None or request_payload["longitude"] is None:
        coordinates = resolve_coordinates(request_payload["hospital_address"], request_payload["city"])
        if coordinates:
            request_payload["latitude"], request_payload["longitude"] = coordinates
    request = create_blood_request(db, user.id, request_payload)
    return request


@router.get("", response_model=list[BloodRequestResponse])
async def list_requests(user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if user.role == "coordinator":
        return db.query(BloodRequest).order_by(BloodRequest.created_at.desc()).all()
    return list_requests_for_user(db, user.id)


@router.get("/{request_id}", response_model=BloodRequestResponse)
async def get_request(request_id: int, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ensure_request_access(db, user, request_id)
    request = get_request_by_id(db, request_id)
    return request


@router.put("/{request_id}", response_model=BloodRequestResponse)
async def update_request(request_id: int, payload: BloodRequestUpdate, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    request = ensure_request_access(db, user, request_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(request, key, value)
    db.commit()
    db.refresh(request)
    return request


@router.post("/{request_id}/cancel")
async def cancel_request(request_id: int, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    request = ensure_request_access(db, user, request_id)
    request.status = "cancelled"
    db.commit()
    return {"message": "Request cancelled."}


@router.post("/{request_id}/match")
async def match_request(request_id: int, user: User = Depends(require_role(["coordinator", "volunteer"])), db: Session = Depends(get_db)):
    request = get_request_by_id(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    matches = find_potential_matches(db, request_id)
    return {"matched_count": len(matches), "matches": matches}


@router.get("/{request_id}/matches")
async def get_matches(request_id: int, user: User = Depends(require_role(["coordinator", "volunteer"])), db: Session = Depends(get_db)):
    request = get_request_by_id(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    matches = db.query(DonorMatch).filter(DonorMatch.request_id == request_id).order_by(DonorMatch.match_score.desc()).all()
    responses = {item.donor_id: item.response for item in db.query(DonorResponse).filter(DonorResponse.request_id == request_id).all()}
    rows = []
    for match in matches:
        donor = db.query(DonorProfile).filter(DonorProfile.user_id == match.donor_id).first()
        donor_user = db.query(User).filter(User.id == match.donor_id).first()
        rows.append({
            "match_id": match.id,
            "request_id": match.request_id,
            "donor_id": match.donor_id,
            "donor_name": donor_user.full_name if donor_user else "Donor",
            "blood_group": donor.blood_group if donor else None,
            "city": donor.city if donor else None,
            "area": donor.area if donor else None,
            "distance_km": match.distance_km,
            "match_score": match.match_score,
            "match_status": match.status,
            "response_status": responses.get(match.donor_id, "pending"),
        })
    accepted_count = sum(row["response_status"] == "accepted" for row in rows)
    declined_count = sum(row["response_status"] == "declined" for row in rows)
    return {"total_matches": len(rows), "pending_responses": len(rows) - accepted_count - declined_count, "accepted_count": accepted_count, "declined_count": declined_count, "matches": rows}


@router.get("/{request_id}/coordination-map")
async def get_coordination_map(request_id: int, user: User = Depends(require_role(["coordinator"])), db: Session = Depends(get_db)):
    request = get_request_by_id(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    matches = db.query(DonorMatch).filter(DonorMatch.request_id == request_id).all()
    responses = {item.donor_id: item.response for item in db.query(DonorResponse).filter(DonorResponse.request_id == request_id).all()}
    donors = []
    for match in matches:
        donor = db.query(DonorProfile).filter(DonorProfile.user_id == match.donor_id).first()
        donor_user = db.query(User).filter(User.id == match.donor_id).first()
        if not donor or donor.latitude is None or donor.longitude is None:
            continue
        donors.append({
            "donor_id": match.donor_id,
            "safe_display_name": donor_user.full_name if donor_user else "Donor",
            "blood_group": donor.blood_group,
            "area": donor.area,
            "city": donor.city,
            "latitude": donor.latitude,
            "longitude": donor.longitude,
            "distance_km": match.distance_km,
            "match_score": match.match_score,
            "response_status": responses.get(match.donor_id, "pending"),
        })
    return {
        "request": {
            "latitude": request.latitude,
            "longitude": request.longitude,
            "hospital_name": request.hospital_name,
            "hospital_address": request.hospital_address,
            "city": request.city,
        },
        "matched_donors": donors,
    }


@router.get("/{request_id}/requester-map")
async def get_requester_map(request_id: int, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    request = ensure_request_access(db, user, request_id)
    if user.role not in {"requester", "coordinator"}:
        raise HTTPException(status_code=403, detail="Only request coordinators can access this map.")
    matches = db.query(DonorMatch).filter(DonorMatch.request_id == request_id).all()
    responses = {item.response for item in db.query(DonorResponse).filter(DonorResponse.request_id == request_id).all()}
    return {
        "request": {"latitude": request.latitude, "longitude": request.longitude, "hospital_name": request.hospital_name, "city": request.city},
        "potential_donors": len(matches),
        "accepted_donors": sum(response == "accepted" for response in responses),
    }


@router.post("/{request_id}/accept")
async def accept_request(request_id: int, user: User = Depends(require_role(["donor"])), db: Session = Depends(get_db)):
    donor = db.query(DonorProfile).filter(DonorProfile.user_id == user.id).first()
    if not donor:
        raise HTTPException(status_code=404, detail="Donor profile not found.")
    match = db.query(DonorMatch).filter(DonorMatch.request_id == request_id, DonorMatch.donor_id == user.id).first()
    if not match:
        raise HTTPException(status_code=403, detail="You are not matched to this request.")
    request = get_request_by_id(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    if request.status != "verified":
        raise HTTPException(status_code=409, detail="This request is not accepting donor responses.")
    existing = db.query(DonorResponse).filter(DonorResponse.request_id == request_id, DonorResponse.donor_id == user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already responded to this request.")
    response = DonorResponse(request_id=request_id, donor_id=user.id, response="accepted")
    db.add(response)
    request.status = "donor_accepted"
    notification = Notification(user_id=request.requester_id, type="donor_accepted", title="Donor accepted request", message="A donor has accepted the blood request.", related_entity_id=request.id)
    db.add(notification)
    for coordinator in db.query(User).filter(User.role == "coordinator", User.active.is_(True)).all():
        db.add(Notification(user_id=coordinator.id, type="donor_accepted", title="Donor accepted request", message="A matched donor accepted a blood request.", related_entity_id=request.id))
    db.commit()
    return {"message": "Request accepted."}


@router.post("/{request_id}/decline")
async def decline_request(request_id: int, user: User = Depends(require_role(["donor"])), db: Session = Depends(get_db)):
    donor = db.query(DonorProfile).filter(DonorProfile.user_id == user.id).first()
    if not donor:
        raise HTTPException(status_code=404, detail="Donor profile not found.")
    match = db.query(DonorMatch).filter(DonorMatch.request_id == request_id, DonorMatch.donor_id == user.id).first()
    if not match:
        raise HTTPException(status_code=403, detail="You are not matched to this request.")
    request = get_request_by_id(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    if request.status != "verified":
        raise HTTPException(status_code=409, detail="This request is not accepting donor responses.")
    existing = db.query(DonorResponse).filter(DonorResponse.request_id == request_id, DonorResponse.donor_id == user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already responded to this request.")
    item = DonorResponse(request_id=request_id, donor_id=user.id, response="declined")
    db.add(item)
    for coordinator in db.query(User).filter(User.role == "coordinator", User.active.is_(True)).all():
        db.add(Notification(user_id=coordinator.id, type="donor_declined", title="Donor declined request", message="A matched donor declined a blood request.", related_entity_id=request.id))
    db.commit()
    return {"message": "Request declined."}


@router.post("/{request_id}/verify")
async def verify_request(request_id: int, user: User = Depends(require_role(["coordinator"])), db: Session = Depends(get_db)):
    request = get_request_by_id(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    was_submitted = request.status == "submitted"
    request.status = "verified"
    request.verified_by = user.id
    request.verified_at = datetime.utcnow()
    db.commit()
    record_audit(db, user.id, "request_verified", "blood_request", request.id, {"request_code": request.request_code, "requester_id": request.requester_id, "status": request.status})
    if was_submitted:
        NotificationService.create(db, request.requester_id, "request_verified", "Request verified", "Your blood request has been verified and donor matching is underway.", request.id)
    return {"message": "Request verified."}


@router.post("/{request_id}/complete")
async def complete_request(request_id: int, user: User = Depends(require_role(["coordinator"])), db: Session = Depends(get_db)):
    request = get_request_by_id(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    if request.status == "fulfilled":
        raise HTTPException(status_code=400, detail="This request has already been completed.")
    if request.status not in {"donor_accepted", "coordination"}:
        raise HTTPException(status_code=409, detail="Only donor-accepted or coordination requests can be fulfilled.")
    request.status = "fulfilled"
    request.fulfilled_at = datetime.utcnow()
    db.commit()
    record_audit(db, user.id, "request_fulfilled", "blood_request", request.id, {"request_code": request.request_code, "fulfilled_at": request.fulfilled_at.isoformat()})
    return {"message": "Request marked fulfilled."}
