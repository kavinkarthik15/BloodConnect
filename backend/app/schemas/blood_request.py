from datetime import datetime

from pydantic import BaseModel, Field


class BloodRequestCreate(BaseModel):
    patient_reference: str = Field(..., min_length=2)
    blood_group: str
    units_required: int = Field(..., ge=1)
    hospital_name: str = Field(..., min_length=2)
    hospital_address: str = Field(..., min_length=2)
    city: str = Field(..., min_length=2)
    latitude: float | None = None
    longitude: float | None = None
    required_at: datetime
    urgency: str = "Normal"
    contact_name: str = Field(..., min_length=2)
    contact_phone: str = Field(..., min_length=7)
    notes: str | None = None


class BloodRequestUpdate(BaseModel):
    patient_reference: str | None = None
    blood_group: str | None = None
    units_required: int | None = Field(default=None, ge=1)
    hospital_name: str | None = None
    hospital_address: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    required_at: datetime | None = None
    urgency: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    notes: str | None = None


class BloodRequestResponse(BaseModel):
    id: int
    request_code: str
    requester_id: int
    patient_reference: str
    blood_group: str
    units_required: int
    hospital_name: str
    hospital_address: str
    city: str
    latitude: float | None = None
    longitude: float | None = None
    required_at: datetime
    urgency: str
    contact_name: str
    contact_phone: str
    notes: str | None = None
    status: str
    verified_by: int | None = None
    verified_at: datetime | None = None
    fulfilled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
