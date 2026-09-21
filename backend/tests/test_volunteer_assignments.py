from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.main import app
from app.models.user import User
from app.services.auth_service import get_password_hash


client = TestClient(app)


def public_account(role: str):
    email = f"{role}-{uuid4().hex}@example.com"
    response = client.post("/api/auth/register", json={
        "full_name": f"Volunteer test {role}",
        "email": email,
        "phone": "9876543210",
        "password": "secret123",
        "role": role,
    })
    return email, response


def seeded_account(role: str):
    email = f"{role}-{uuid4().hex}@example.com"
    db = SessionLocal()
    db.add(User(full_name=f"Seeded {role}", email=email, phone="9876543210", password_hash=get_password_hash("secret123"), role=role))
    db.commit()
    db.close()
    return email


def token(email: str):
    response = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def auth(access_token: str):
    return {"Authorization": f"Bearer {access_token}"}


def test_coordinator_assigns_and_volunteer_completes_assignment():
    requester, requester_response = public_account("requester")
    volunteer, volunteer_response = public_account("volunteer")
    assert requester_response.status_code == 201
    assert volunteer_response.status_code == 403
    volunteer = seeded_account("volunteer")
    coordinator = seeded_account("coordinator")

    request = client.post("/api/requests", headers=auth(token(requester)), json={
        "patient_reference": "Volunteer assignment test",
        "blood_group": "O+",
        "units_required": 1,
        "hospital_name": "Assignment Hospital",
        "hospital_address": "1 Assignment Street",
        "city": "Bengaluru",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "required_at": "2026-09-25T12:00:00",
        "urgency": "Urgent",
        "contact_name": "Assignment Contact",
        "contact_phone": "9876543210",
    })
    assert request.status_code == 200
    request_id = request.json()["id"]
    volunteer_id = client.get("/api/auth/me", headers=auth(token(volunteer))).json()["id"]
    coordinator_headers = auth(token(coordinator))

    assigned = client.post(f"/api/volunteers/requests/{request_id}/assignments", headers=coordinator_headers, json={"volunteer_id": volunteer_id})
    assert assigned.status_code == 201, assigned.text
    assignment_id = assigned.json()["id"]

    duplicate = client.post(f"/api/volunteers/requests/{request_id}/assignments", headers=coordinator_headers, json={"volunteer_id": volunteer_id})
    assert duplicate.status_code == 409

    volunteer_headers = auth(token(volunteer))
    assert client.patch(f"/api/volunteers/me/assignments/{assignment_id}/status?status=accepted", headers=volunteer_headers).status_code == 200
    assert client.patch(f"/api/volunteers/me/assignments/{assignment_id}/status?status=in_progress", headers=volunteer_headers).status_code == 200
    assert client.patch(f"/api/volunteers/me/assignments/{assignment_id}/status?status=completed", headers=volunteer_headers).status_code == 200
    invalid = client.patch(f"/api/volunteers/me/assignments/{assignment_id}/status?status=assigned", headers=volunteer_headers)
    assert invalid.status_code == 409


def test_requester_and_donor_cannot_assign_volunteer():
    requester, _ = public_account("requester")
    donor, _ = public_account("donor")
    volunteer = seeded_account("volunteer")
    volunteer_id = client.get("/api/auth/me", headers=auth(token(volunteer))).json()["id"]
    payload = {"volunteer_id": volunteer_id}
    assert client.post("/api/volunteers/requests/2/assignments", headers=auth(token(requester)), json=payload).status_code == 403
    assert client.post("/api/volunteers/requests/2/assignments", headers=auth(token(donor)), json=payload).status_code == 403
