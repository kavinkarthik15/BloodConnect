from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import SessionLocal
from app.main import app
from app.models.auth_security import BrowserSession
from app.models.audit_log import AuditLog
from app.models.blood_request import BloodRequest
from app.models.donation_confirmation import DonationConfirmation
from app.models.donor import DonorProfile
from app.models.match import DonorMatch
from app.models.notification import Notification
from app.models.response import DonorResponse
from app.models.user import User
from app.services.auth_service import create_access_token
from app.services.request_expiration_service import expire_due_requests


client = TestClient(app)


def _user(role: str) -> tuple[User, dict[str, str]]:
    db = SessionLocal()
    user = User(
        full_name=f"Lifecycle {role}",
        email=f"{role}-{uuid4().hex}@example.org",
        phone="9876543210",
        password_hash="test-only",
        role=role,
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    session_id = str(uuid4())
    db.add(BrowserSession(
        id=session_id,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    ))
    db.commit()
    token = create_access_token(user.email, session_id=session_id)
    headers = {"Authorization": f"Bearer {token}"}
    db.expunge(user)
    db.close()
    return user, headers


def _create_request(
    headers: dict[str, str],
    units: int = 2,
    required_at: datetime | None = None,
    with_coordinates: bool = True,
) -> dict:
    deadline = required_at or (datetime.now(timezone.utc) + timedelta(days=5))
    response = client.post("/api/requests", headers=headers, json={
        "patient_reference": "TEST-REFERENCE",
        "blood_group": "O+",
        "units_required": units,
        "hospital_name": "Test Hospital",
        "hospital_address": "1 Test Road",
        "city": f"Lifecycle City {uuid4().hex[:6]}",
        "latitude": 12.9,
        "longitude": 77.5,
        "required_at": deadline.isoformat(),
        "urgency": "Emergency",
        "contact_name": "Test Contact",
        "contact_phone": "9999999999",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["escalation_status"] == "emergency"
    if not with_coordinates:
        db = SessionLocal()
        request = db.query(BloodRequest).filter(BloodRequest.id == data["id"]).first()
        request.latitude = None
        request.longitude = None
        db.commit()
        db.close()
    return data


def _donor(city: str) -> tuple[User, dict[str, str]]:
    user, headers = _user("donor")
    db = SessionLocal()
    db.add(DonorProfile(
        user_id=user.id,
        blood_group="O+",
        city=city,
        available=True,
        verified=True,
    ))
    db.commit()
    db.close()
    return user, headers


def _prepare_request(
    requester_headers: dict[str, str],
    coordinator_headers: dict[str, str],
    donor_users: list[User],
    with_coordinates: bool = True,
    units: int = 2,
) -> dict:
    request_data = _create_request(requester_headers, units=units, with_coordinates=with_coordinates)
    db = SessionLocal()
    request = db.query(BloodRequest).filter(BloodRequest.id == request_data["id"]).first()
    city = request.city
    db.close()
    for donor in donor_users:
        db = SessionLocal()
        profile = db.query(DonorProfile).filter(DonorProfile.user_id == donor.id).first()
        profile.city = city
        db.commit()
        db.close()
    verified = client.post(f"/api/requests/{request_data['id']}/verify", headers=coordinator_headers)
    assert verified.status_code == 200, verified.text
    matched = client.post(f"/api/requests/{request_data['id']}/match", headers=coordinator_headers)
    assert matched.status_code == 200, matched.text
    assert matched.json()["matched_count"] >= len(donor_users)
    return request_data


def test_multiple_donor_offers_require_separate_confirmations_and_never_overfill():
    requester, requester_headers = _user("requester")
    coordinator, coordinator_headers = _user("coordinator")
    donor_one, donor_one_headers = _donor("pending")
    donor_two, donor_two_headers = _donor("pending")
    donor_three, donor_three_headers = _donor("pending")
    request_data = _prepare_request(requester_headers, coordinator_headers, [donor_one, donor_two, donor_three])
    request_id = request_data["id"]

    response_one = client.post(f"/api/requests/{request_id}/accept", headers=donor_one_headers)
    response_two = client.post(f"/api/requests/{request_id}/accept", headers=donor_two_headers)
    assert response_one.status_code == response_two.status_code == 200
    assert client.post(f"/api/requests/{request_id}/accept", headers=donor_one_headers).status_code == 409

    status_response = client.get(f"/api/requests/{request_id}", headers=requester_headers)
    assert status_response.json()["status"] == "coordinating"
    assert status_response.json()["units_confirmed"] == 0

    first_confirmation = client.post(
        f"/api/requests/{request_id}/donations/{donor_one.id}/confirm",
        headers=coordinator_headers,
        json={"units_confirmed": 1, "verification_source": "Test authorized blood bank"},
    )
    assert first_confirmation.status_code == 200, first_confirmation.text
    partial = client.get(f"/api/requests/{request_id}", headers=requester_headers).json()
    assert partial["status"] == "partially_fulfilled"
    assert partial["units_confirmed"] == 1
    assert client.post(f"/api/requests/{request_id}/accept", headers=donor_three_headers).status_code == 200
    assert client.get(f"/api/requests/{request_id}", headers=requester_headers).json()["status"] == "partially_fulfilled"

    overfill = client.post(
        f"/api/requests/{request_id}/donations/{donor_two.id}/confirm",
        headers=coordinator_headers,
        json={"units_confirmed": 2, "verification_source": "Test authorized blood bank"},
    )
    assert overfill.status_code == 409
    final_confirmation = client.post(
        f"/api/requests/{request_id}/donations/{donor_two.id}/confirm",
        headers=coordinator_headers,
        json={"units_confirmed": 1, "verification_source": "Test authorized blood bank"},
    )
    assert final_confirmation.status_code == 200, final_confirmation.text
    fulfilled = client.get(f"/api/requests/{request_id}", headers=requester_headers).json()
    assert fulfilled["status"] == "fulfilled"
    assert fulfilled["units_confirmed"] == fulfilled["units_required"] == 2
    assert fulfilled["legacy_fulfillment_unverified"] is False

    db = SessionLocal()
    assert db.query(DonationConfirmation).filter(DonationConfirmation.request_id == request_id).count() == 2
    assert db.query(AuditLog).filter(AuditLog.entity_id == str(request_id), AuditLog.action == "donation_confirmed").count() == 2
    assert db.query(Notification).filter(
        Notification.user_id == requester.id,
        Notification.related_entity_id == request_id,
        Notification.type == "donation_confirmed",
    ).count() == 2
    assert db.query(Notification).filter(
        Notification.user_id == requester.id,
        Notification.related_entity_id == request_id,
        Notification.type == "donor_accepted",
    ).count() == 3
    assert db.query(Notification).filter(
        Notification.user_id == donor_one.id,
        Notification.related_entity_id == request_id,
        Notification.type == "donation_confirmed",
    ).count() == 1
    db.close()


def test_request_cancellation_checks_ownership_and_confirmed_units():
    requester, requester_headers = _user("requester")
    other_requester, other_headers = _user("requester")
    coordinator, coordinator_headers = _user("coordinator")
    donor, donor_headers = _donor("pending")
    cancellable = _create_request(requester_headers)
    assert client.post(f"/api/requests/{cancellable['id']}/cancel", headers=requester_headers).status_code == 200
    assert client.get(f"/api/requests/{cancellable['id']}", headers=requester_headers).json()["status"] == "cancelled"
    request_data = _prepare_request(requester_headers, coordinator_headers, [donor])
    request_id = request_data["id"]

    assert client.post(f"/api/requests/{request_id}/cancel", headers=other_headers).status_code == 403
    assert client.post(f"/api/requests/{request_id}/accept", headers=donor_headers).status_code == 200
    confirmed = client.post(
        f"/api/requests/{request_id}/donations/{donor.id}/confirm",
        headers=coordinator_headers,
        json={"units_confirmed": 1, "verification_source": "Test authorized blood bank"},
    )
    assert confirmed.status_code == 200
    assert client.post(f"/api/requests/{request_id}/withdraw", headers=donor_headers).status_code == 409
    assert client.post(f"/api/requests/{request_id}/cancel", headers=requester_headers).status_code == 409
    assert client.post(f"/api/requests/{request_id}/cancel", headers=coordinator_headers).status_code == 409
    assert client.post(f"/api/requests/{request_id}/close", headers=coordinator_headers).status_code == 200
    db = SessionLocal()
    request = db.query(BloodRequest).filter(BloodRequest.id == request_id).first()
    assert request.status == "closed"
    assert request.units_confirmed == 1
    db.close()


def test_donor_can_withdraw_only_own_unconfirmed_offer_and_expired_requests_escalate():
    requester, requester_headers = _user("requester")
    coordinator, coordinator_headers = _user("coordinator")
    donor, donor_headers = _donor("pending")
    other_donor, other_donor_headers = _donor("pending")
    request_data = _prepare_request(requester_headers, coordinator_headers, [donor, other_donor])
    request_id = request_data["id"]
    assert client.post(f"/api/requests/{request_id}/accept", headers=donor_headers).status_code == 200
    assert client.post(f"/api/requests/{request_id}/withdraw", headers=other_donor_headers).status_code == 409
    assert client.post(f"/api/requests/{request_id}/withdraw", headers=donor_headers).status_code == 200
    assert client.get(f"/api/requests/{request_id}", headers=requester_headers).json()["status"] == "verified"

    expired_request = _create_request(
        requester_headers,
        required_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    expired = client.get(f"/api/requests/{expired_request['id']}", headers=requester_headers)
    assert expired.status_code == 200
    assert expired.json()["status"] == "expired"
    assert expired.json()["escalation_status"] == "emergency_overdue"
    assert expired_request["escalation_status"] == "emergency"

    scheduled_expiry = _create_request(
        requester_headers,
        required_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db = SessionLocal()
    assert expire_due_requests(db) == 1
    assert expire_due_requests(db) == 0
    assert db.query(Notification).filter(
        Notification.user_id == requester.id,
        Notification.related_entity_id == scheduled_expiry["id"],
        Notification.type == "request_expired",
    ).count() == 1
    db.close()


def test_expiry_cli_rolls_back_state_audit_and_notification_on_database_failure(monkeypatch):
    requester, requester_headers = _user("requester")
    request_data = _create_request(
        requester_headers,
        required_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db = SessionLocal()

    def fail_commit():
        raise SQLAlchemyError("synthetic commit failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    from app.cli import expire_requests

    monkeypatch.setattr(expire_requests, "SessionLocal", lambda: db)
    with pytest.raises(SQLAlchemyError):
        expire_requests.main()

    verification_db = SessionLocal()
    request = verification_db.query(BloodRequest).filter(
        BloodRequest.id == request_data["id"],
    ).one()
    assert request.status == "submitted"
    assert verification_db.query(AuditLog).filter(
        AuditLog.entity_id == str(request_data["id"]),
        AuditLog.action == "request_expired",
    ).count() == 0
    assert verification_db.query(Notification).filter(
        Notification.user_id == requester.id,
        Notification.related_entity_id == request_data["id"],
        Notification.type == "request_expired",
    ).count() == 0
    verification_db.close()


def test_coordinator_can_record_pre_deadline_offer_after_expiration():
    requester, requester_headers = _user("requester")
    coordinator, coordinator_headers = _user("coordinator")
    donor, donor_headers = _donor("pending")
    request_data = _prepare_request(requester_headers, coordinator_headers, [donor], with_coordinates=True, units=1)
    request_id = request_data["id"]
    assert client.post(f"/api/requests/{request_id}/accept", headers=donor_headers).status_code == 200

    db = SessionLocal()
    request = db.query(BloodRequest).filter(BloodRequest.id == request_id).first()
    request.required_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    db.close()

    confirmation = client.post(
        f"/api/requests/{request_id}/donations/{donor.id}/confirm",
        headers=coordinator_headers,
        json={"units_confirmed": 1, "verification_source": "Test authorized blood bank"},
    )
    assert confirmation.status_code == 200, confirmation.text
    request_status = client.get(f"/api/requests/{request_id}", headers=requester_headers).json()
    assert request_status["status"] == "fulfilled"
    assert request_status["escalation_status"] == "emergency_overdue"


def test_location_fallback_matches_same_city_without_fabricating_distance():
    requester, requester_headers = _user("requester")
    coordinator, coordinator_headers = _user("coordinator")
    donor, _ = _donor("pending")
    request_data = _prepare_request(requester_headers, coordinator_headers, [donor], with_coordinates=False)
    db = SessionLocal()
    match = db.query(DonorMatch).filter(
        DonorMatch.request_id == request_data["id"],
        DonorMatch.donor_id == donor.id,
    ).first()
    assert match is not None
    assert match.distance_km is None
    db.close()


def test_legacy_completed_endpoint_cannot_mark_offers_fulfilled():
    requester, requester_headers = _user("requester")
    coordinator, coordinator_headers = _user("coordinator")
    request_data = _create_request(requester_headers)
    assert client.post(f"/api/requests/{request_data['id']}/verify", headers=coordinator_headers).status_code == 200
    assert client.post(f"/api/requests/{request_data['id']}/complete", headers=coordinator_headers).status_code == 409


def test_donation_confirmation_is_coordinator_only_and_request_data_is_owner_scoped():
    requester, requester_headers = _user("requester")
    another_requester, another_requester_headers = _user("requester")
    coordinator, coordinator_headers = _user("coordinator")
    donor, donor_headers = _donor("pending")
    request_data = _prepare_request(requester_headers, coordinator_headers, [donor], units=1)
    request_id = request_data["id"]
    assert client.get(f"/api/requests/{request_id}", headers=another_requester_headers).status_code == 403
    assert client.get(f"/api/requests/{request_id}/requester-map", headers=another_requester_headers).status_code == 403
    assert client.get(f"/api/requests/{request_id}/coordination-map", headers=requester_headers).status_code == 403
    assert client.get("/api/donors/management", headers=requester_headers).status_code == 403
    assert client.post(
        f"/api/requests/{request_id}/donations/{donor.id}/confirm",
        headers=requester_headers,
        json={"units_confirmed": 1, "verification_source": "Test source"},
    ).status_code == 403
    assert client.post(
        f"/api/requests/{request_id}/donations/{donor.id}/confirm",
        headers=donor_headers,
        json={"units_confirmed": 1, "verification_source": "Test source"},
    ).status_code == 403
    assert client.get(f"/api/donors/me/matches/{request_id}", headers=donor_headers).status_code == 200
    other_donor, other_donor_headers = _donor("unmatched")
    assert client.get(f"/api/donors/me/matches/{request_id}", headers=other_donor_headers).status_code == 403


def test_simultaneous_donors_and_duplicate_acceptances_are_serialized_and_deduplicated():
    requester, requester_headers = _user("requester")
    coordinator, coordinator_headers = _user("coordinator")
    donor, donor_headers = _donor("pending")
    second_donor, second_donor_headers = _donor("pending")
    request_data = _prepare_request(requester_headers, coordinator_headers, [donor, second_donor], units=2)
    request_id = request_data["id"]
    barrier = Barrier(2)

    def accept(headers):
        barrier.wait()
        return client.post(f"/api/requests/{request_id}/accept", headers=headers).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(accept, [donor_headers, second_donor_headers]))
    assert statuses == [200, 200]

    duplicate_barrier = Barrier(2)

    def duplicate_accept():
        duplicate_barrier.wait()
        return client.post(f"/api/requests/{request_id}/accept", headers=donor_headers).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        duplicate_statuses = list(executor.map(lambda _index: duplicate_accept(), range(2)))
    assert duplicate_statuses == [409, 409]

    db = SessionLocal()
    assert db.query(DonorResponse).filter(
        DonorResponse.request_id == request_id,
    ).count() == 2
    assert db.query(Notification).filter(
        Notification.user_id == requester.id,
        Notification.related_entity_id == request_id,
        Notification.type == "donor_accepted",
    ).count() == 2
    assert db.query(Notification).filter(
        Notification.user_id == coordinator.id,
        Notification.related_entity_id == request_id,
        Notification.type == "donor_accepted",
    ).count() == 2
    db.close()


def test_sqlite_foreign_key_enforcement_is_enabled_for_application_sessions():
    db = SessionLocal()
    assert db.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
    db.close()


def test_simultaneous_donation_confirmations_cannot_overfill_request():
    requester, requester_headers = _user("requester")
    coordinator, coordinator_headers = _user("coordinator")
    donor_one, donor_one_headers = _donor("pending")
    donor_two, donor_two_headers = _donor("pending")
    request_data = _prepare_request(
        requester_headers,
        coordinator_headers,
        [donor_one, donor_two],
        units=1,
    )
    request_id = request_data["id"]
    assert client.post(f"/api/requests/{request_id}/accept", headers=donor_one_headers).status_code == 200
    assert client.post(f"/api/requests/{request_id}/accept", headers=donor_two_headers).status_code == 200
    barrier = Barrier(2)

    def confirm(donor_id: int):
        barrier.wait()
        return client.post(
            f"/api/requests/{request_id}/donations/{donor_id}/confirm",
            headers=coordinator_headers,
            json={"units_confirmed": 1, "verification_source": "Test authorized blood bank"},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(confirm, [donor_one.id, donor_two.id]))
    assert sorted(statuses) == [200, 409]
    db = SessionLocal()
    request = db.query(BloodRequest).filter(BloodRequest.id == request_id).first()
    assert request.units_confirmed == request.units_required == 1
    assert db.query(DonationConfirmation).filter(DonationConfirmation.request_id == request_id).count() == 1
    db.close()
