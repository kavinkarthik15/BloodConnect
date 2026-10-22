from math import atan2, cos, radians, sin, sqrt

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.donor import DonorProfile
from app.models.blood_request import BloodRequest
from app.models.match import DonorMatch
from app.models.notification import Notification
from app.services.compatibility_service import get_compatibility_type, is_potentially_compatible


def haversine_km(lat1, lon1, lat2, lon2):
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 9999.0
    radius = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * radius * atan2(sqrt(a), sqrt(1 - a))


def find_potential_matches(db: Session, request_id: int, radius_km: float = 25.0):
    request = db.query(BloodRequest).filter(BloodRequest.id == request_id).first()
    if not request:
        return []

    donors = db.query(DonorProfile).filter(DonorProfile.available.is_(True), DonorProfile.verified.is_(True)).all()
    matches = []
    for donor in donors:
        if not donor.blood_group:
            continue
        if not is_potentially_compatible(donor.blood_group, request.blood_group):
            continue
        has_request_location = request.latitude is not None and request.longitude is not None
        has_donor_location = donor.latitude is not None and donor.longitude is not None
        if has_request_location and has_donor_location:
            distance = haversine_km(request.latitude, request.longitude, donor.latitude, donor.longitude)
            if distance > radius_km:
                continue
        elif donor.city.strip().casefold() != request.city.strip().casefold():
            continue
        else:
            distance = None
        compatibility_score = 60 if donor.blood_group == request.blood_group else 45
        distance_score = max(0, 40 * (1 - (distance / radius_km))) if distance is not None else 0
        score = round(compatibility_score + distance_score, 2)
        matches.append({
            "donor_id": donor.user_id,
            "distance_km": round(distance, 2) if distance is not None else None,
            "match_score": score,
            "compatibility_type": get_compatibility_type(donor.blood_group, request.blood_group),
            "status": "pending",
        })
    matches.sort(key=lambda item: (-item["match_score"], item["distance_km"] is None, item["distance_km"] or 0))
    for match in matches:
        existing = db.query(DonorMatch).filter(
            DonorMatch.request_id == request.id,
            DonorMatch.donor_id == match["donor_id"],
        ).first()
        if existing:
            continue
        try:
            with db.begin_nested():
                record = DonorMatch(
                    request_id=request.id,
                    donor_id=match["donor_id"],
                    compatibility_type=match["compatibility_type"],
                    distance_km=match["distance_km"],
                    match_score=match["match_score"],
                    status=match["status"],
                )
                db.add(record)
                db.flush()
                already_notified = db.query(Notification.id).filter(
                    Notification.user_id == match["donor_id"],
                    Notification.related_entity_id == request.id,
                    Notification.type == "potential_match",
                ).first()
                if not already_notified:
                    db.add(Notification(
                        user_id=match["donor_id"],
                        type="potential_match",
                        title="Potential Blood Donation Request",
                        message="A potentially compatible blood request is available in your area.",
                        related_entity_id=request.id,
                    ))
        except IntegrityError:
            if not db.query(DonorMatch.id).filter(
                DonorMatch.request_id == request.id,
                DonorMatch.donor_id == match["donor_id"],
            ).first():
                raise
    db.commit()
    return matches
