from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, func

from app.db.database import Base


class BloodRequest(Base):
    __tablename__ = "blood_requests"

    id = Column(Integer, primary_key=True, index=True)
    request_code = Column(String, unique=True, index=True, nullable=False)
    requester_id = Column(Integer, nullable=False, index=True)
    patient_reference = Column(String, nullable=False)
    blood_group = Column(String, nullable=False)
    units_required = Column(Integer, nullable=False)
    hospital_name = Column(String, nullable=False)
    hospital_address = Column(String, nullable=False)
    city = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    required_at = Column(DateTime(timezone=True), nullable=False)
    urgency = Column(String, nullable=False, default="Normal")
    contact_name = Column(String, nullable=False)
    contact_phone = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="submitted")
    verified_by = Column(Integer, nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    fulfilled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
