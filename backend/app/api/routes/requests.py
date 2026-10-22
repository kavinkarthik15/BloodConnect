from datetime import datetime, timezone
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_role
from app.db.database import get_db
from app.models.blood_request import BloodRequest
from app.models.donor import DonorProfile
from app.models.donation_confirmation import DonationConfirmation
from app.models.match import DonorMatch
from app.models.notification import Notification
from app.models.response import DonorResponse
from app.models.user import User
from app.models.volunteer_assignment import VolunteerAssignment
from app.schemas.blood_request import BloodRequestCreate, BloodRequestResponse, BloodRequestUpdate
from app.schemas.donation_confirmation import DonationConfirmationCreate
from app.services.audit_service import record_audit
from app.services.blood_request_service import create_blood_request, ensure_request_access, get_request_by_id, list_requests_for_user
from app.services.geocoding_service import resolve_coordinates
from app.services.matching_service import find_potential_matches
from app.services.request_expiration_service import expire_due_requests
from app.services.rate_limit_service import limit_matching

router = APIRouter(prefix="/api/requests", tags=["requests"])

ACTIVE_ASSIGNMENT_STATUSES = {"assigned", "accepted", "in_progress"}
OPEN_REQUEST_STATUSES = {"submitted", "verified", "coordinating", "partially_fulfilled"}
SQLITE_REQUEST_WRITE_LOCK = Lock()


async def serialize_sqlite_request_write(db: Session = Depends(get_db)):
    if db.bind and db.bind.dialect.name == "sqlite":
        SQLITE_REQUEST_WRITE_LOCK.acquire()
        try:
            yield
        finally:
            SQLITE_REQUEST_WRITE_LOCK.release()
        return
    yield


def ensure_volunteer_assignment_access(db: Session, request_id: int, user: User):
    if user.role != "volunteer":
        return
    assignment = db.query(VolunteerAssignment).filter(
        VolunteerAssignment.request_id == request_id,
        VolunteerAssignment.volunteer_id == user.id,
        VolunteerAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
    ).first()
    if not assignment:
        raise HTTPException(status_code=403, detail="You are not assigned to this request.")


def expire_request_if_due(db: Session, request: BloodRequest, actor_id: int | None = None) -> bool:
    if request.status not in OPEN_REQUEST_STATUSES:
        return False
    required_at = request.required_at
    if required_at.tzinfo is None:
        required_at = required_at.replace(tzinfo=timezone.utc)
    if required_at > datetime.now(timezone.utc):
        return False

    expire_due_requests(db, now=datetime.now(timezone.utc), request_id=request.id, actor_user_id=actor_id)
    return True


def get_live_request(db: Session, request_id: int, actor_id: int | None = None, lock: bool = False):
    query = db.query(BloodRequest).filter(BloodRequest.id == request_id)
    if lock:
        query = query.with_for_update()
    request = query.first()
    if request:
        expire_request_if_due(db, request, actor_id)
    return request


def enqueue_notification(
    db: Session,
    user_id: int,
    notification_type: str,
    title: str,
    message: str,
    request_id: int,
    event_key: str | None = None,
):
    query = db.query(Notification.id)
    if event_key is not None:
        event_key = f"{event_key}:recipient:{user_id}"
        query = query.filter(Notification.dedupe_key == event_key)
    else:
        query = query.filter(
            Notification.user_id == user_id,
            Notification.type == notification_type,
            Notification.related_entity_id == request_id,
        )
    exists = query.first()
    if not exists:
        db.add(Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            related_entity_id=request_id,
            dedupe_key=event_key,
        ))


def raise_response_conflict(db: Session, error: IntegrityError | OperationalError):
    db.rollback()
    if isinstance(error, IntegrityError):
        raise HTTPException(status_code=409, detail="A response for this donor and request already exists.") from None
    if db.bind and db.bind.dialect.name == "sqlite" and "locked" in str(error.orig).casefold():
        raise HTTPException(status_code=409, detail="The request was updated concurrently. Please retry.") from None
    raise error


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
        priority = case(
            (BloodRequest.urgency.ilike("emergency"), 0),
            (BloodRequest.urgency.ilike("urgent"), 1),
            else_=2,
        )
        return db.query(BloodRequest).order_by(priority, BloodRequest.created_at.desc()).all()
    return list_requests_for_user(db, user.id)


@router.get("/{request_id}", response_model=BloodRequestResponse)
async def get_request(request_id: int, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ensure_request_access(db, user, request_id)
    request = get_live_request(db, request_id, user.id)
    return request


@router.put("/{request_id}", response_model=BloodRequestResponse)
async def update_request(request_id: int, payload: BloodRequestUpdate, user: User = Depends(get_current_active_user), db: Session = Depends(get_db), _: None = Depends(serialize_sqlite_request_write)):
    request = ensure_request_access(db, user, request_id)
    get_live_request(db, request_id, user.id, lock=True)
    db.refresh(request)
    if request.status not in {"submitted"}:
        raise HTTPException(status_code=409, detail="Only submitted requests can be edited.")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("units_required", request.units_required) < request.units_confirmed:
        raise HTTPException(status_code=409, detail="Requested units cannot be lower than confirmed units.")
    for key, value in changes.items():
        setattr(request, key, value)
    if "urgency" in changes:
        request.escalation_status = "emergency" if str(changes["urgency"]).casefold() == "emergency" else "normal"
    record_audit(db, user.id, "request_updated", "blood_request", request.id, {"updated_fields": sorted(changes)})
    db.commit()
    db.refresh(request)
    return request


@router.post("/{request_id}/cancel")
async def cancel_request(request_id: int, user: User = Depends(get_current_active_user), db: Session = Depends(get_db), _: None = Depends(serialize_sqlite_request_write)):
    request = get_request_by_id(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    if user.role == "requester" and request.requester_id != user.id:
        raise HTTPException(status_code=403, detail="You are not authorized to access this request.")
    if user.role not in {"requester", "coordinator"}:
        raise HTTPException(status_code=403, detail="You are not authorized to cancel this request.")
    request = get_live_request(db, request_id, user.id, lock=True)
    if request.status not in OPEN_REQUEST_STATUSES:
        raise HTTPException(status_code=409, detail="This request is not open for cancellation.")
    if user.role == "requester" and request.units_confirmed:
        raise HTTPException(status_code=409, detail="Requesters may cancel only before any units are confirmed.")
    if user.role == "coordinator" and request.units_confirmed:
        raise HTTPException(status_code=409, detail="Requests with confirmed units cannot be cancelled; close the case instead.")
    request.status = "cancelled"
    record_audit(db, user.id, "request_cancelled", "blood_request", request.id, {"units_confirmed": request.units_confirmed})
    enqueue_notification(db, request.requester_id, "request_cancelled", "Blood request cancelled", "Your blood request has been cancelled.", request.id)
    db.commit()
    return {"message": "Request cancelled."}


@router.post("/{request_id}/close")
async def close_request(request_id: int, user: User = Depends(require_role(["coordinator"])), db: Session = Depends(get_db), _: None = Depends(serialize_sqlite_request_write)):
    request = get_live_request(db, request_id, user.id, lock=True)
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    if request.status not in OPEN_REQUEST_STATUSES:
        raise HTTPException(status_code=409, detail="This request is not open for closure.")
    request.status = "closed"
    record_audit(db, user.id, "request_closed", "blood_request", request.id, {"units_confirmed": request.units_confirmed})
    enqueue_notification(db, request.requester_id, "request_closed", "Blood request closed", "A coordinator closed this blood request.", request.id)
    db.commit()
    return {"message": "Request closed."}


@router.post("/{request_id}/match")
async def match_request(request_id: int, _: None = Depends(limit_matching), user: User = Depends(require_role(["coordinator", "volunteer"])), db: Session = Depends(get_db)):
    request = get_request_by_id(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    if request.status not in {"verified", "coordinating", "partially_fulfilled"}:
        raise HTTPException(status_code=409, detail="Only verified requests can be matched.")
    ensure_volunteer_assignment_access(db, request_id, user)
    request = get_live_request(db, request_id, user.id)
    if request.status not in {"verified", "coordinating", "partially_fulfilled"}:
        raise HTTPException(status_code=409, detail="Only verified requests can be matched.")
    matches = find_potential_matches(db, request_id)
    return {"matched_count": len(matches), "matches": matches}


@router.get("/{request_id}/matches")
async def get_matches(request_id: int, user: User = Depends(require_role(["coordinator", "volunteer"])), db: Session = Depends(get_db)):
    request = get_request_by_id(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    ensure_volunteer_assignment_access(db, request_id, user)
    request = get_live_request(db, request_id, user.id)
    if user.role == "volunteer" and request.status in {"submitted", "cancelled"}:
        raise HTTPException(status_code=409, detail="Matches are unavailable for this request.")
    matches = db.query(DonorMatch).filter(DonorMatch.request_id == request_id).order_by(DonorMatch.match_score.desc()).all()
    responses = {item.donor_id: item.response for item in db.query(DonorResponse).filter(DonorResponse.request_id == request_id).all()}
    confirmations = {
        item.donor_id: item.units_confirmed
        for item in db.query(DonationConfirmation).filter(DonationConfirmation.request_id == request_id).all()
    }
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
            "donation_confirmed": match.donor_id in confirmations,
            "units_confirmed": confirmations.get(match.donor_id, 0),
        })
    accepted_count = sum(row["response_status"] == "accepted" for row in rows)
    declined_count = sum(row["response_status"] == "declined" for row in rows)
    withdrawn_count = sum(row["response_status"] == "withdrawn" for row in rows)
    pending_count = sum(row["response_status"] == "pending" for row in rows)
    return {
        "total_matches": len(rows),
        "pending_responses": pending_count,
        "accepted_count": accepted_count,
        "declined_count": declined_count,
        "withdrawn_count": withdrawn_count,
        "matches": rows,
    }


@router.get("/{request_id}/coordination-map")
async def get_coordination_map(request_id: int, user: User = Depends(require_role(["coordinator"])), db: Session = Depends(get_db)):
    request = get_live_request(db, request_id, user.id)
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
    request = get_live_request(db, request_id, user.id)
    if user.role not in {"requester", "coordinator"}:
        raise HTTPException(status_code=403, detail="Only request coordinators can access this map.")
    matches = db.query(DonorMatch).filter(DonorMatch.request_id == request_id).all()
    responses = [item.response for item in db.query(DonorResponse).filter(DonorResponse.request_id == request_id).all()]
    return {
        "request": {"latitude": request.latitude, "longitude": request.longitude, "hospital_name": request.hospital_name, "city": request.city},
        "potential_donors": len(matches),
        "accepted_donors": sum(response == "accepted" for response in responses),
    }


@router.post("/{request_id}/accept")
async def accept_request(request_id: int, user: User = Depends(require_role(["donor"])), db: Session = Depends(get_db), _: None = Depends(serialize_sqlite_request_write)):
    donor = db.query(DonorProfile).filter(DonorProfile.user_id == user.id).first()
    if not donor:
        raise HTTPException(status_code=404, detail="Donor profile not found.")
    match = db.query(DonorMatch).filter(DonorMatch.request_id == request_id, DonorMatch.donor_id == user.id).first()
    if not match:
        raise HTTPException(status_code=403, detail="You are not matched to this request.")
    request = get_live_request(db, request_id, user.id, lock=True)
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    if request.status not in {"verified", "coordinating", "partially_fulfilled"}:
        raise HTTPException(status_code=409, detail="This request is not accepting donor responses.")
    existing = db.query(DonorResponse).filter(DonorResponse.request_id == request_id, DonorResponse.donor_id == user.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="You have already responded to this request.")
    response = DonorResponse(request_id=request_id, donor_id=user.id, response="accepted")
    db.add(response)
    if request.status == "verified":
        request.status = "coordinating"
    try:
        record_audit(db, user.id, "donor_response_accepted", "blood_request", request.id, {"donor_id": user.id})
        event_key = f"donor-response:{request.id}:{user.id}"
        enqueue_notification(db, request.requester_id, "donor_accepted", "Donor accepted request", "A donor has offered to coordinate for this request. This is not confirmation of donation.", request.id, event_key)
        for coordinator in db.query(User).filter(User.role == "coordinator", User.active.is_(True)).all():
            enqueue_notification(db, coordinator.id, "donor_accepted", "Donor accepted request", "A matched donor offered to coordinate for a blood request.", request.id, event_key)
        db.commit()
    except (IntegrityError, OperationalError) as exc:
        raise_response_conflict(db, exc)
    return {"message": "Request accepted."}


@router.post("/{request_id}/decline")
async def decline_request(request_id: int, user: User = Depends(require_role(["donor"])), db: Session = Depends(get_db), _: None = Depends(serialize_sqlite_request_write)):
    donor = db.query(DonorProfile).filter(DonorProfile.user_id == user.id).first()
    if not donor:
        raise HTTPException(status_code=404, detail="Donor profile not found.")
    match = db.query(DonorMatch).filter(DonorMatch.request_id == request_id, DonorMatch.donor_id == user.id).first()
    if not match:
        raise HTTPException(status_code=403, detail="You are not matched to this request.")
    request = get_live_request(db, request_id, user.id, lock=True)
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    if request.status not in {"verified", "coordinating", "partially_fulfilled"}:
        raise HTTPException(status_code=409, detail="This request is not accepting donor responses.")
    existing = db.query(DonorResponse).filter(DonorResponse.request_id == request_id, DonorResponse.donor_id == user.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="You have already responded to this request.")
    item = DonorResponse(request_id=request_id, donor_id=user.id, response="declined")
    db.add(item)
    try:
        record_audit(db, user.id, "donor_response_declined", "blood_request", request.id)
        for coordinator in db.query(User).filter(User.role == "coordinator", User.active.is_(True)).all():
            event_key = f"donor-response-declined:{request.id}:{user.id}"
            enqueue_notification(db, coordinator.id, "donor_declined", "Donor declined request", "A matched donor declined a blood request.", request.id, event_key)
        db.commit()
    except (IntegrityError, OperationalError) as exc:
        raise_response_conflict(db, exc)
    return {"message": "Request declined."}


@router.post("/{request_id}/withdraw")
async def withdraw_response(request_id: int, user: User = Depends(require_role(["donor"])), db: Session = Depends(get_db), _: None = Depends(serialize_sqlite_request_write)):
    response = db.query(DonorResponse).filter(
        DonorResponse.request_id == request_id,
        DonorResponse.donor_id == user.id,
        DonorResponse.response == "accepted",
    ).first()
    if not response:
        raise HTTPException(status_code=409, detail="There is no accepted response to withdraw.")
    request = get_live_request(db, request_id, user.id, lock=True)
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    if request.status not in OPEN_REQUEST_STATUSES:
        raise HTTPException(status_code=409, detail="This request is no longer open for withdrawal.")
    response = db.query(DonorResponse).filter(
        DonorResponse.request_id == request_id,
        DonorResponse.donor_id == user.id,
    ).with_for_update().first()
    if not response or response.response != "accepted":
        raise HTTPException(status_code=409, detail="There is no accepted response to withdraw.")
    confirmation = db.query(DonationConfirmation.id).filter(
        DonationConfirmation.request_id == request_id,
        DonationConfirmation.donor_id == user.id,
    ).first()
    if confirmation:
        raise HTTPException(status_code=409, detail="A response cannot be withdrawn after donation confirmation.")
    response.response = "withdrawn"
    response.responded_at = datetime.now(timezone.utc)
    remaining_acceptances = db.query(DonorResponse.id).filter(
        DonorResponse.request_id == request_id,
        DonorResponse.response == "accepted",
        DonorResponse.donor_id != user.id,
    ).first()
    if not remaining_acceptances and request.units_confirmed == 0 and request.status == "coordinating":
        request.status = "verified"
    record_audit(db, user.id, "donor_response_withdrawn", "blood_request", request.id, {"donor_id": user.id})
    for coordinator in db.query(User).filter(User.role == "coordinator", User.active.is_(True)).all():
        event_key = f"donor-response-withdrawn:{request.id}:{user.id}"
        enqueue_notification(db, coordinator.id, "donor_withdrew", "Donor withdrew response", "A donor withdrew an accepted response.", request.id, event_key)
    db.commit()
    return {"message": "Donor response withdrawn."}


@router.post("/{request_id}/verify")
async def verify_request(request_id: int, user: User = Depends(require_role(["coordinator"])), db: Session = Depends(get_db), _: None = Depends(serialize_sqlite_request_write)):
    request = get_live_request(db, request_id, user.id, lock=True)
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    if request.status != "submitted":
        raise HTTPException(status_code=409, detail="Only submitted requests can be verified.")
    request.status = "verified"
    request.verified_by = user.id
    request.verified_at = datetime.now(timezone.utc)
    record_audit(db, user.id, "request_verified", "blood_request", request.id, {"request_code": request.request_code, "requester_id": request.requester_id, "status": request.status})
    enqueue_notification(db, request.requester_id, "request_verified", "Request verified", "Your blood request has been verified and donor matching is underway.", request.id)
    db.commit()
    return {"message": "Request verified."}


@router.post("/{request_id}/donations/{donor_id}/confirm")
async def confirm_donation(
    request_id: int,
    donor_id: int,
    payload: DonationConfirmationCreate,
    user: User = Depends(require_role(["coordinator"])),
    db: Session = Depends(get_db),
    _: None = Depends(serialize_sqlite_request_write),
):
    request = get_live_request(db, request_id, user.id, lock=True)
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    if request.status not in {"coordinating", "partially_fulfilled", "expired"}:
        raise HTTPException(status_code=409, detail="This request cannot receive donation confirmations.")
    donor_response = db.query(DonorResponse).filter(
        DonorResponse.request_id == request_id,
        DonorResponse.donor_id == donor_id,
        DonorResponse.response == "accepted",
    ).first()
    if not donor_response:
        raise HTTPException(status_code=409, detail="Donation can only be confirmed for a donor with an accepted response.")
    remaining_units = request.units_required - request.units_confirmed
    if payload.units_confirmed > remaining_units:
        raise HTTPException(status_code=409, detail="Confirmed units cannot exceed the remaining requested units.")

    confirmation = DonationConfirmation(
        request_id=request_id,
        donor_id=donor_id,
        confirmed_by=user.id,
        units_confirmed=payload.units_confirmed,
        verification_source=payload.verification_source,
        reference=payload.reference,
        notes=payload.notes,
    )
    db.add(confirmation)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A donation outcome for this donor and request is already recorded.") from None
    new_total = BloodRequest.units_confirmed + payload.units_confirmed
    outcome = db.query(BloodRequest).filter(
        BloodRequest.id == request_id,
        BloodRequest.status.in_({"coordinating", "partially_fulfilled", "expired"}),
        new_total <= BloodRequest.units_required,
    ).update({
        BloodRequest.units_confirmed: new_total,
        BloodRequest.status: case(
            (new_total == BloodRequest.units_required, "fulfilled"),
            (BloodRequest.status == "expired", "expired"),
            else_="partially_fulfilled",
        ),
        BloodRequest.fulfilled_at: case(
            (new_total == BloodRequest.units_required, func.now()),
            else_=None,
        ),
    }, synchronize_session=False)
    if outcome != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="The request changed concurrently or no requested units remain.")
    db.refresh(request)
    record_audit(db, user.id, "donation_confirmed", "blood_request", request.id, {
        "donor_id": donor_id,
        "units_confirmed": payload.units_confirmed,
        "total_units_confirmed": request.units_confirmed,
        "verification_source": payload.verification_source,
    })
    event_key = f"donation-confirmed:{request.id}:{donor_id}"
    enqueue_notification(db, request.requester_id, "donation_confirmed", "Donation outcome confirmed", f"A coordinator confirmed {payload.units_confirmed} unit(s) for request {request.request_code}.", request.id, event_key)
    enqueue_notification(db, donor_id, "donation_confirmed", "Donation outcome confirmed", f"A coordinator recorded {payload.units_confirmed} confirmed unit(s) for request {request.request_code}.", request.id, event_key)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A donation outcome for this donor and request is already recorded.") from None
    return {
        "message": "Donation outcome recorded.",
        "units_confirmed": request.units_confirmed,
        "units_required": request.units_required,
        "status": request.status,
    }


@router.post("/{request_id}/complete")
async def complete_request(request_id: int, user: User = Depends(require_role(["coordinator"])), db: Session = Depends(get_db)):
    request = get_live_request(db, request_id, user.id)
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found.")
    raise HTTPException(status_code=409, detail="Fulfillment requires coordinator-recorded donation confirmations.")
