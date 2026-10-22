from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app
from app.db.database import SessionLocal
from app.models.user import User
from app.services.auth_service import get_password_hash

client = TestClient(app)


def register_user(email: str, password: str, role: str = "requester"):
    if role not in {"requester", "donor"}:
        db = SessionLocal()
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            db.close()
            return type("SeedResponse", (), {"status_code": 201, "text": ""})()
        user = User(
            full_name="Demo User",
            email=email,
            phone="9876543210",
            password_hash=get_password_hash(password),
            role=role,
        )
        db.add(user)
        db.commit()
        db.close()
        return type("SeedResponse", (), {"status_code": 201, "text": ""})()
    return client.post(
        "/api/auth/register",
        json={
            "full_name": "Demo User",
            "email": email,
            "phone": "9876543210",
            "password": password,
            "role": role,
        },
    )


def login(email: str, password: str):
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    return response.json()["access_token"]


def auth_headers(email: str, password: str):
    return {"Authorization": f"Bearer {login(email, password)}"}


def unique_email(prefix: str):
    return f"{prefix}-{uuid4().hex}@example.com"


def test_registration_and_login():
    email = unique_email("requester")
    response = register_user(email, "SafePassword123", "requester")
    assert response.status_code == 201, response.text

    login_response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "SafePassword123"},
    )
    assert login_response.status_code == 200, login_response.text
    assert "access_token" in login_response.json()


def test_requester_can_create_and_view_request():
    email = unique_email("requester2")
    register_user(email, "SafePassword123", "requester")
    token = login(email, "SafePassword123")

    response = client.post(
        "/api/requests",
        json={
            "patient_reference": "Patient A",
            "blood_group": "O+",
            "units_required": 2,
            "hospital_name": "Demo General Hospital",
            "hospital_address": "1 Main Street",
            "city": "Bengaluru",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "required_at": "2027-09-25T12:00:00",
            "urgency": "Emergency",
            "contact_name": "Request Contact",
            "contact_phone": "9900000000",
            "notes": "Need urgent support.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "submitted"
    assert data["request_code"].startswith("BCR-")

    list_response = client.get("/api/requests", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200
    assert len(list_response.json()) >= 1


def test_coordinator_can_verify_request_and_match_donors():
    requester_email = unique_email("requester3")
    donor_email = "donor1@example.com"
    coordinator_email = "coordinator@example.com"

    register_user(requester_email, "SafePassword123", "requester")
    register_user(donor_email, "SafePassword123", "donor")
    register_user(coordinator_email, "SafePassword123", "coordinator")

    requester_token = login(requester_email, "SafePassword123")
    donor_token = login(donor_email, "SafePassword123")
    coordinator_token = login(coordinator_email, "SafePassword123")

    request_response = client.post(
        "/api/requests",
        json={
            "patient_reference": "Patient B",
            "blood_group": "O+",
            "units_required": 2,
            "hospital_name": "Demo General Hospital",
            "hospital_address": "2 Main Street",
            "city": "Bengaluru",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "required_at": "2027-09-26T12:00:00",
            "urgency": "Emergency",
            "contact_name": "Request Contact",
            "contact_phone": "9900000001",
            "notes": "Need urgent support.",
        },
        headers={"Authorization": f"Bearer {requester_token}"},
    )
    request_id = request_response.json()["id"]

    verify_response = client.post(f"/api/requests/{request_id}/verify", headers={"Authorization": f"Bearer {coordinator_token}"})
    assert verify_response.status_code == 200, verify_response.text
    assert verify_response.json()["message"] == "Request verified."

    donor_profile_response = client.post(
        "/api/donors/me",
        json={
            "blood_group": "O+",
            "city": "Bengaluru",
            "area": "Koramangala",
            "latitude": 12.9352,
            "longitude": 77.6245,
            "available": True,
            "verified": True,
        },
        headers={"Authorization": f"Bearer {donor_token}"},
    )
    assert donor_profile_response.status_code == 200, donor_profile_response.text
    donor_id = client.get("/api/auth/me", headers={"Authorization": f"Bearer {donor_token}"}).json()["id"]
    verification_response = client.patch(f"/api/donors/management/{donor_id}/verification?verified=true", headers={"Authorization": f"Bearer {coordinator_token}"})
    assert verification_response.status_code == 200, verification_response.text

    match_response = client.post(f"/api/requests/{request_id}/match", headers={"Authorization": f"Bearer {coordinator_token}"})
    assert match_response.status_code == 200, match_response.text
    assert "matched_count" in match_response.json()


def test_donor_can_accept_and_decline_request():
    requester_email = unique_email("requester4")
    donor_email = "donor2@example.com"
    coordinator_email = "coordinator2@example.com"

    register_user(requester_email, "SafePassword123", "requester")
    register_user(donor_email, "SafePassword123", "donor")
    register_user(coordinator_email, "SafePassword123", "coordinator")

    requester_token = login(requester_email, "SafePassword123")
    donor_token = login(donor_email, "SafePassword123")
    coordinator_token = login(coordinator_email, "SafePassword123")

    request_response = client.post(
        "/api/requests",
        json={
            "patient_reference": "Patient C",
            "blood_group": "A+",
            "units_required": 1,
            "hospital_name": "City Hospital",
            "hospital_address": "5 Park Street",
            "city": "Hyderabad",
            "latitude": 17.4065,
            "longitude": 78.4772,
            "required_at": "2027-09-27T12:00:00",
            "urgency": "Urgent",
            "contact_name": "Request Contact",
            "contact_phone": "9900000002",
        },
        headers={"Authorization": f"Bearer {requester_token}"},
    )
    request_id = request_response.json()["id"]
    client.post(f"/api/requests/{request_id}/verify", headers={"Authorization": f"Bearer {coordinator_token}"})

    donor_profile_response = client.post(
        "/api/donors/me",
        json={
            "blood_group": "A+",
            "city": "Hyderabad",
            "area": "Madhapur",
            "latitude": 17.4401,
            "longitude": 78.3911,
            "available": True,
            "verified": True,
        },
        headers={"Authorization": f"Bearer {donor_token}"},
    )
    assert donor_profile_response.status_code == 200
    donor_id = client.get("/api/auth/me", headers={"Authorization": f"Bearer {donor_token}"}).json()["id"]
    verification_response = client.patch(f"/api/donors/management/{donor_id}/verification?verified=true", headers={"Authorization": f"Bearer {coordinator_token}"})
    assert verification_response.status_code == 200, verification_response.text

    match_response = client.post(f"/api/requests/{request_id}/match", headers={"Authorization": f"Bearer {coordinator_token}"})
    assert match_response.status_code == 200, match_response.text
    assert match_response.json()["matched_count"] >= 1

    accept_response = client.post(f"/api/requests/{request_id}/accept", headers={"Authorization": f"Bearer {donor_token}"})
    assert accept_response.status_code == 200, accept_response.text
    assert accept_response.json()["message"] == "Request accepted."

    duplicate = client.post(f"/api/requests/{request_id}/accept", headers={"Authorization": f"Bearer {donor_token}"})
    assert duplicate.status_code == 409
