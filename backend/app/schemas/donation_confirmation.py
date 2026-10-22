from pydantic import BaseModel, Field


class DonationConfirmationCreate(BaseModel):
    units_confirmed: int = Field(..., ge=1)
    verification_source: str = Field(..., min_length=3, max_length=100)
    reference: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=1000)
