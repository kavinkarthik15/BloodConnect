from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_role
from app.db.database import get_db
from app.models.campaign import Campaign
from app.models.user import User
from app.services.audit_service import record_audit

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])
VALID_STATUSES = {"planned", "published", "completed", "cancelled"}


class CampaignPayload(BaseModel):
    title: str = Field(..., min_length=2)
    description: str | None = None
    location: str = Field(..., min_length=2)
    campaign_date: datetime
    participant_count: int = Field(default=0, ge=0)
    registered_donors: int = Field(default=0, ge=0)
    units_recorded: int = Field(default=0, ge=0)


def campaign_payload(campaign: Campaign):
    return {
        "id": campaign.id,
        "title": campaign.title,
        "description": campaign.description,
        "location": campaign.location,
        "campaign_date": campaign.campaign_date,
        "organizer_id": campaign.organizer_id,
        "status": campaign.status,
        "participant_count": campaign.participant_count,
        "registered_donors": campaign.registered_donors,
        "units_recorded": campaign.units_recorded,
        "created_at": campaign.created_at,
    }


@router.get("")
async def list_public_campaigns(db: Session = Depends(get_db)):
    return [campaign_payload(item) for item in db.query(Campaign).filter(Campaign.status == "published").order_by(Campaign.campaign_date.asc()).all()]


@router.get("/management/all")
async def list_campaigns_for_coordinator(user: User = Depends(require_role(["coordinator"])), db: Session = Depends(get_db)):
    return [campaign_payload(item) for item in db.query(Campaign).order_by(Campaign.campaign_date.desc()).all()]


@router.get("/{campaign_id}")
async def get_public_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.status == "published").first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Published campaign not found.")
    return campaign_payload(campaign)


@router.post("", status_code=201)
async def create_campaign(payload: CampaignPayload, user: User = Depends(require_role(["coordinator"])), db: Session = Depends(get_db)):
    campaign = Campaign(**payload.model_dump(), organizer_id=user.id, status="planned")
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    record_audit(db, user.id, "campaign_created", "campaign", campaign.id, {"title": campaign.title, "location": campaign.location})
    return campaign_payload(campaign)


@router.patch("/{campaign_id}/status")
async def update_campaign_status(campaign_id: int, status: str, user: User = Depends(require_role(["coordinator"])), db: Session = Depends(get_db)):
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid campaign status.")
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    previous_status = campaign.status
    campaign.status = status
    db.commit()
    db.refresh(campaign)
    record_audit(db, user.id, "campaign_status_changed", "campaign", campaign.id, {"from_status": previous_status, "to_status": status})
    return campaign_payload(campaign)