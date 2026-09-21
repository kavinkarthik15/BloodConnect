from sqlalchemy import Column, DateTime, Float, Integer, String, func

from app.db.database import Base


class DonorMatch(Base):
    __tablename__ = "donor_matches"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, nullable=False, index=True)
    donor_id = Column(Integer, nullable=False, index=True)
    compatibility_type = Column(String, nullable=False)
    distance_km = Column(Float, nullable=True)
    match_score = Column(Float, nullable=False, default=0.0)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
