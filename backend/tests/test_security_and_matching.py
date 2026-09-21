from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.main import app
from app.models.user import User
from app.models.donor import DonorProfile
from app.models.notification import Notification
from app.services.auth_service import get_password_hash


client = TestClient(app)


def account(role: str):
    email = f"{role}-{uuid4().hex}@example.com"
    response = client.post("/api/auth/register", json={
        "full_name": f"Test {role}",
        "email": email,
        "phone": "9876543210",
        "password": "secret123",
        "role": role,
    })
    return email, response


def seed_privileged(role: str):
    email = f"{role}-{uuid4().hex}@example.com"
    db = SessionLocal()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        db.close()
        return email
    db.add(User(full_name=f"Test {role}", email=email, phone="9876543210", password_hash=get_password_hash("secret123"), role=role))
    db.commit()
    db.close()
    return email


def token(email: str):
    response = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def headers(access_token: str):
    return {"Authorization": f"Bearer {access_token}"}


def test_public_registration_only_allows_requester_and_donor():
    assert account("requester")[1].status_code == 201
    assert account("donor")[1].status_code == 201
    assert account("volunteer")[1].status_code == 403
    assert account("coordinator")[1].status_code == 403
    assert account("admin")[1].status_code == 403


def test_unmatched_donor_cannot_accept_or_decline():
    requester, requester_response = account("requester")
    donor, donor_response = account("donor")
    coordinator = seed_privileged("coordinator")
    assert requester_response.status_code == 201
    assert donor_response.status_code == 201

    request = client.post("/api/requests", headers=headers(token(requester)), json={
        "patient_reference": "Unmatched Test",
        "blood_group": "O+",
        "units_required": 1,
        "hospital_name": "Test Hospital",
        "hospital_address": "1 Test Street",
        "city": "Bengaluru",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "required_at": "2026-09-25T12:00:00",
        "urgency": "Urgent",
        "contact_name": "Test Contact",
        "contact_phone": "9876543210",
    })
    assert request.status_code == 200
    request_id = request.json()["id"]
    coordinator_headers = headers(token(coordinator))
    assert client.post(f"/api/requests/{request_id}/verify", headers=coordinator_headers).status_code == 200

    donor_id = client.get("/api/auth/me", headers=headers(token(donor))).json()["id"]
    db = SessionLocal()
    db.add(DonorProfile(user_id=donor_id, blood_group="O+", city="Hyderabad", area="Madhapur", latitude=17.4, longitude=78.4, available=True, verified=True))
    db.commit()
    db.close()

    donor_headers = headers(token(donor))
    assert client.post(f"/api/requests/{request_id}/accept", headers=donor_headers).status_code == 403
    assert client.post(f"/api/requests/{request_id}/decline", headers=donor_headers).status_code == 403


def test_matching_without_coordinates_returns_no_fake_distance(monkeypatch):
    requester, _ = account("requester")
    coordinator = seed_privileged("coordinator")
    request = client.post("/api/requests", headers=headers(token(requester)), json={
        "patient_reference": "Location Test",
        "blood_group": "O+",
        "units_required": 1,
        "hospital_name": "Test Hospital",
        "hospital_address": "Unknown",
        "city": "Unknown",
        "required_at": "2026-09-25T12:00:00",
        "urgency": "Normal",
        "contact_name": "Test Contact",
        "contact_phone": "9876543210",
    })
    assert request.status_code == 200
    request_id = request.json()["id"]
    assert client.post(f"/api/requests/{request_id}/verify", headers=headers(token(coordinator))).status_code == 200
    result = client.post(f"/api/requests/{request_id}/match", headers=headers(token(coordinator)))
    assert result.status_code == 200
    assert result.json() == {"matched_count": 0, "matches": []}


def test_donor_cannot_self_verify_but_coordinator_can():
    donor, response = account("donor")
    assert response.status_code == 201
    donor_token = token(donor)
    profile = client.post("/api/donors/me", headers=headers(donor_token), json={"blood_group": "O+", "city": "Bengaluru", "verified": True})
    assert profile.status_code == 200
    assert profile.json()["verified"] is False

    coordinator = seed_privileged("coordinator")
    donor_id = profile.json()["user_id"]
    verified = client.patch(f"/api/donors/management/{donor_id}/verification?verified=true", headers=headers(token(coordinator)))
    assert verified.status_code == 200
    assert verified.json()["verified"] is True


def test_notifications_are_private_and_unread_count_is_scoped():
    first, first_response = account("requester")
    second, second_response = account("requester")
    assert first_response.status_code == 201
    assert second_response.status_code == 201
    db = SessionLocal()
    first_id = db.query(User).filter(User.email == first).first().id
    second_id = db.query(User).filter(User.email == second).first().id
    db.add_all([
        Notification(user_id=first_id, type="system", title="Private one", message="One"),
        Notification(user_id=second_id, type="system", title="Private two", message="Two"),
    ])
    db.commit()
    db.close()
    first_token = token(first)
    assert client.get("/api/notifications", headers=headers(first_token)).json()[0]["title"] == "Private one"
    assert client.get("/api/notifications/unread-count", headers=headers(first_token)).json()["count"] == 1
    second_notification = client.get("/api/notifications", headers=headers(token(second))).json()[0]
    assert client.patch(f"/api/notifications/{second_notification['id']}/read", headers=headers(first_token)).status_code == 404


def test_map_endpoint_is_coordinator_only():
    requester, response = account("requester")
    assert response.status_code == 201
    request = client.post("/api/requests", headers=headers(token(requester)), json={
        "patient_reference": "Map privacy test", "blood_group": "O+", "units_required": 1,
        "hospital_name": "Map Hospital", "hospital_address": "1 Map Street", "city": "Bengaluru",
        "latitude": 12.9716, "longitude": 77.5946, "required_at": "2026-09-25T12:00:00",
        "urgency": "Normal", "contact_name": "Contact", "contact_phone": "9876543210",
    })
    assert request.status_code == 200
    request_id = request.json()["id"]
    assert client.get(f"/api/requests/{request_id}/coordination-map", headers=headers(token(requester))).status_code == 403