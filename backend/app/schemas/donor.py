from datetime import date

from pydantic import BaseModel, Field


class DonorProfileCreate(BaseModel):
    blood_group: str
    city: str = Field(..., min_length=2)
    area: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    available: bool = True
    last_donation_date: date | None = None
    verified: bool = False


class DonorProfileUpdate(BaseModel):
    blood_group: str | None = None
    city: str | None = None
    area: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    available: bool | None = None
    last_donation_date: date | None = None
    verified: bool | None = None


class DonorProfileResponse(BaseModel):
    id: int
    user_id: int
    blood_group: str
    city: str
    area: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    available: bool
    last_donation_date: date | None = None
    verified: bool

    class Config:
        from_attributes = True
