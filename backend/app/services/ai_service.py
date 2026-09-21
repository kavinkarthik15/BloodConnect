import json
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.blood_request import BloodRequest
from app.models.campaign import Campaign
from app.models.user import User
from app.models.volunteer_assignment import VolunteerAssignment


class AIService:
    MEDICAL_BOUNDARY_PATTERNS = (
        "medically eligible",
        "eligible to donate",
        "safe to donate",
        "safely receive",
        "safe to receive",
        "diagnose",
        "diagnosis",
        "treatment",
        "transfusion safety",
        "blood compatibility",
        "should this patient receive",
        "should i donate",
        "can this patient safely",
        "am i medically eligible",
    )

    @staticmethod
    def is_configured() -> bool:
        return bool(settings.ai_enabled and settings.ai_provider and settings.ai_base_url and settings.ai_api_key and settings.ai_model)

    @staticmethod
    def _medical_boundary_refusal(message: str) -> dict[str, Any]:
        lower = message.lower()
        if any(pattern in lower for pattern in AIService.MEDICAL_BOUNDARY_PATTERNS):
            return {
                "response": "I can provide general education about BloodConnect and blood donation workflows, but final medical decisions about donor eligibility, treatment, diagnosis, transfusion safety, or compatibility must be made by a qualified healthcare professional or authorized blood bank.",
                "provider_available": False,
            }
        return None

    @staticmethod
    def build_role_context(user: User, db: Session) -> dict[str, Any]:
        if user.role == "requester":
            requests = db.query(BloodRequest).filter(BloodRequest.requester_id == user.id).all()
            return {
                "role": "requester",
                "active_requests": sum(item.status not in {"fulfilled", "cancelled"} for item in requests),
                "latest_request_status": requests[0].status if requests else "none",
                "published_campaigns": db.query(Campaign).filter(Campaign.status == "published").count(),
            }

        if user.role == "donor":
            donor_profile = db.query(User).filter(User.id == user.id).first()
            return {
                "role": "donor",
                "profile_exists": donor_profile is not None,
                "accepted_requests": db.query(BloodRequest).count(),
                "published_campaigns": db.query(Campaign).filter(Campaign.status == "published").count(),
            }

        if user.role == "volunteer":
            assignments = db.query(VolunteerAssignment).filter(VolunteerAssignment.volunteer_id == user.id).all()
            return {
                "role": "volunteer",
                "active_assignments": sum(item.status in {"assigned", "accepted", "in_progress"} for item in assignments),
                "completed_assignments": sum(item.status == "completed" for item in assignments),
                "published_campaigns": db.query(Campaign).filter(Campaign.status == "published").count(),
            }

        if user.role == "coordinator":
            return {
                "role": "coordinator",
                "total_requests": db.query(BloodRequest).count(),
                "urgent_requests": db.query(BloodRequest).filter(BloodRequest.urgency.in_(["Urgent", "Emergency"])).count(),
                "active_assignments": db.query(VolunteerAssignment).filter(VolunteerAssignment.status.in_(["assigned", "accepted", "in_progress"])).count(),
                "published_campaigns": db.query(Campaign).filter(Campaign.status == "published").count(),
            }

        return {"role": user.role, "status": "minimal"}

    @staticmethod
    def _safe_failure(message: str, provider_available: bool = False) -> dict[str, Any]:
        return {"response": message, "provider_available": provider_available}

    @staticmethod
    def generate_chat_response(user: User, db: Session, message: str) -> dict[str, Any]:
        trimmed = message.strip()
        if not trimmed:
            return AIService._safe_failure("Please enter a message for the assistant.")

        boundary_refusal = AIService._medical_boundary_refusal(trimmed)
        if boundary_refusal is not None:
            return boundary_refusal

        if not settings.ai_enabled:
            return AIService._safe_failure("AI assistance is currently unavailable because the feature is disabled or not configured.", False)

        if not settings.ai_provider or not settings.ai_api_key or not settings.ai_base_url:
            return AIService._safe_failure("AI assistance is not configured. Add the provider settings to enable it.", False)

        context = AIService.build_role_context(user, db)
        provider = settings.ai_provider
        base_url = settings.ai_base_url.rstrip('/')
        url = f"{base_url}/chat/completions" if not base_url.endswith("/chat/completions") else base_url

        prompt = (
            "You are a BloodConnect assistant. Help users with BloodConnect usage, request status, campaigns, volunteer workflows, and general blood donation awareness. "
            "Do not provide medical eligibility decisions, treatment advice, compatibility decisions, or emergency clinical guidance. "
            "For medical eligibility or compatibility questions, tell the user to confirm with qualified healthcare professionals or an authorized blood bank. "
            f"Current user context: {json.dumps(context, default=str)}"
        )

        try:
            response = httpx.post(
                url,
                headers={"Authorization": f"Bearer {settings.ai_api_key}", "Content-Type": "application/json"},
                json={
                    "model": settings.ai_model,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": trimmed[:1500]},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 250,
                },
                timeout=settings.ai_timeout_seconds,
            )
        except httpx.TimeoutException:
            return AIService._safe_failure("AI assistance timed out. Please try again shortly.", False)
        except httpx.RequestError:
            return AIService._safe_failure("AI assistance is temporarily unavailable. Please try again later.", False)

        if response.status_code in {401, 403}:
            return AIService._safe_failure("AI provider authorization failed. Please contact an administrator.", False)
        if response.status_code == 429:
            return AIService._safe_failure("AI assistance is rate-limited. Please try again later.", False)
        if 500 <= response.status_code < 600:
            return AIService._safe_failure("The AI provider is currently unavailable. Please try again later.", False)

        try:
            payload = response.json()
        except ValueError:
            return AIService._safe_failure("The AI provider returned an invalid response. Please try again later.", False)

        text = None
        if isinstance(payload, dict):
            choices = payload.get("choices") or []
            if choices:
                first = choices[0]
                if isinstance(first, dict):
                    message_block = first.get("message") or {}
                    if isinstance(message_block, dict):
                        text = message_block.get("content")
        if not text:
            return AIService._safe_failure("AI assistance could not produce a valid response. Please try again later.", False)

        safe_response = str(text).strip()
        if not safe_response:
            return AIService._safe_failure("AI assistance returned an empty response.", False)

        return {"response": safe_response, "provider_available": True, "provider": provider}
