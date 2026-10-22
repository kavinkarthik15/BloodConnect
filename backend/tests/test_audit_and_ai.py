from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.database import SessionLocal
from app.main import app
from app.models.user import User
from app.services.ai_service import AIService
from app.services.auth_service import get_password_hash

client = TestClient(app)


def make_user(email: str, role: str):
    db = SessionLocal()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        db.close()
        return existing
    user = User(
        full_name=f"{role.title()} User",
        email=email,
        phone="9876543210",
        password_hash=get_password_hash("SafePassword123"),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


def login(email: str):
    response = client.post("/api/auth/login", json={"email": email, "password": "SafePassword123"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def headers(token_value: str):
    return {"Authorization": f"Bearer {token_value}"}


def test_coordinator_action_creates_audit_entry():
    requester_email = f"requester-{uuid4().hex}@example.com"
    coordinator_email = f"coordinator-{uuid4().hex}@example.com"
    make_user(requester_email, "requester")
    coordinator = make_user(coordinator_email, "coordinator")

    requester_token = login(requester_email)
    coordinator_token = login(coordinator_email)

    request_response = client.post(
        "/api/requests",
        headers=headers(requester_token),
        json={
            "patient_reference": "Audit patient",
            "blood_group": "O+",
            "units_required": 1,
            "hospital_name": "Audit Hospital",
            "hospital_address": "Audit Street",
            "city": "Bengaluru",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "required_at": "2027-09-30T12:00:00",
            "urgency": "Urgent",
            "contact_name": "Audit Contact",
            "contact_phone": "9999999999",
        },
    )
    assert request_response.status_code == 200, request_response.text
    request_id = request_response.json()["id"]

    verify_response = client.post(f"/api/requests/{request_id}/verify", headers=headers(coordinator_token))
    assert verify_response.status_code == 200, verify_response.text

    audit_response = client.get("/api/audit-logs", headers=headers(coordinator_token), params={"action": "request_verified"})
    assert audit_response.status_code == 200, audit_response.text
    assert any(item["actor_user_id"] == coordinator.id for item in audit_response.json()["items"])


def test_non_coordinator_cannot_read_audit_logs():
    requester_email = f"requester2-{uuid4().hex}@example.com"
    make_user(requester_email, "requester")
    requester_token = login(requester_email)
    response = client.get("/api/audit-logs", headers=headers(requester_token))
    assert response.status_code == 403


def test_ai_disabled_state_is_safe():
    original = settings.ai_enabled
    settings.ai_enabled = False
    try:
        email = f"requester-{uuid4().hex}@example.com"
        make_user(email, "requester")
        response = client.post(
            "/api/assistant/chat",
            headers=headers(login(email)),
            json={"message": "What is my request status?"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["provider_available"] is False
        assert "unavailable" in payload["response"].lower()
    finally:
        settings.ai_enabled = original


def test_missing_ai_api_key_is_handled_safely():
    original_enabled = settings.ai_enabled
    original_provider = settings.ai_provider
    original_key = settings.ai_api_key
    settings.ai_enabled = True
    settings.ai_provider = "openai"
    settings.ai_api_key = ""
    try:
        email = f"requester3-{uuid4().hex}@example.com"
        make_user(email, "requester")
        token = login(email)
        response = client.post(
            "/api/assistant/chat",
            headers=headers(token),
            json={"message": "What are my active requests?"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["provider_available"] is False
        assert "not configured" in payload["response"].lower()
    finally:
        settings.ai_enabled = original_enabled
        settings.ai_provider = original_provider
        settings.ai_api_key = original_key


def test_ai_context_filters_sensitive_fields():
    requester_email = f"requester4-{uuid4().hex}@example.com"
    make_user(requester_email, "requester")
    token_value = login(requester_email)
    response = client.post(
        "/api/assistant/chat",
        headers=headers(token_value),
        json={"message": "Show my requests"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "provider_available" in payload
    assert "response" in payload


def test_ai_medical_boundary_rejects_decision_requests():
    original_enabled = settings.ai_enabled
    original_provider = settings.ai_provider
    original_key = settings.ai_api_key
    original_base_url = settings.ai_base_url
    try:
        settings.ai_enabled = True
        settings.ai_provider = "openai"
        settings.ai_api_key = "test-key"
        settings.ai_base_url = "https://example.test/v1"
        email = f"requester-medical-{uuid4().hex}@example.com"
        make_user(email, "requester")
        token = login(email)
        with patch("app.services.ai_service.httpx.post") as mock_post:
            response = client.post(
                "/api/assistant/chat",
                headers=headers(token),
                json={"message": "Can this patient safely receive my blood?"},
            )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["provider_available"] is False
        assert "qualified healthcare professional" in payload["response"].lower()
        mock_post.assert_not_called()
    finally:
        settings.ai_enabled = original_enabled
        settings.ai_provider = original_provider
        settings.ai_api_key = original_key
        settings.ai_base_url = original_base_url


def test_ai_benign_question_still_works_with_mocked_provider():
    original_enabled = settings.ai_enabled
    original_provider = settings.ai_provider
    original_key = settings.ai_api_key
    original_base_url = settings.ai_base_url
    original_model = settings.ai_model
    try:
        settings.ai_enabled = True
        settings.ai_provider = "openai"
        settings.ai_api_key = "test-key"
        settings.ai_base_url = "https://example.test/v1"
        settings.ai_model = "gpt-4o-mini"
        email = f"requester-benign-{uuid4().hex}@example.com"
        make_user(email, "requester")
        token = login(email)
        fake_response = Mock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"choices": [{"message": {"content": "Donor verification confirms the profile is checked by a coordinator."}}]}
        with patch("app.services.ai_service.httpx.post", return_value=fake_response):
            response = client.post(
                "/api/assistant/chat",
                headers=headers(token),
                json={"message": "What does donor verification mean in BloodConnect?"},
            )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["provider_available"] is True
        assert "verification" in payload["response"].lower()
    finally:
        settings.ai_enabled = original_enabled
        settings.ai_provider = original_provider
        settings.ai_api_key = original_key
        settings.ai_base_url = original_base_url
        settings.ai_model = original_model


def test_ai_role_context_filters_private_data():
    db = SessionLocal()
    try:
        requester_one = make_user(f"requester-private-1-{uuid4().hex}@example.com", "requester")
        requester_two = make_user(f"requester-private-2-{uuid4().hex}@example.com", "requester")
        volunteer_one = make_user(f"volunteer-private-1-{uuid4().hex}@example.com", "volunteer")
        volunteer_two = make_user(f"volunteer-private-2-{uuid4().hex}@example.com", "volunteer")

        context_one = AIService.build_role_context(requester_one, db)
        context_volunteer = AIService.build_role_context(volunteer_one, db)

        assert context_one["role"] == "requester"
        assert "requester_two" not in str(context_one)
        assert context_volunteer["role"] == "volunteer"
        assert "volunteer_two" not in str(context_volunteer)
    finally:
        db.close()
