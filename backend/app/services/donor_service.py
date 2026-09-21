from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.donor import DonorProfile
from app.models.user import User
from app.schemas.donor import DonorProfileCreate, DonorProfileUpdate


def get_donor_profile(db: Session, user_id: int):
    return db.query(DonorProfile).filter(DonorProfile.user_id == user_id).first()


def create_or_update_donor_profile(db: Session, user_id: int, data: DonorProfileCreate | DonorProfileUpdate):
    donor = get_donor_profile(db, user_id)
    if donor:
        for key, value in data.model_dump(exclude_unset=True, exclude={"verified"}).items():
            setattr(donor, key, value)
        db.commit()
        db.refresh(donor)
        return donor

    donor = DonorProfile(user_id=user_id, **data.model_dump(exclude={"verified"}))
    db.add(donor)
    db.commit()
    db.refresh(donor)
    return donor


def set_donor_availability(db: Session, user_id: int, available: bool):
    donor = get_donor_profile(db, user_id)
    if not donor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Donor profile not found.")
    donor.available = available
    donor.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(donor)
    return donor


def ensure_user_has_donor_role(user: User):
    if user.role not in {"donor", "coordinator", "volunteer"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Donor profile access is restricted to donor role users.")
