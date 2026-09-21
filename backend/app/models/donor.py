from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, func

from app.db.database import Base


class DonorProfile(Base):
    __tablename__ = "donor_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)
    blood_group = Column(String, nullable=False)
    city = Column(String, nullable=False)
    area = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    available = Column(Boolean, default=True)
    last_donation_date = Column(Date, nullable=True)
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
