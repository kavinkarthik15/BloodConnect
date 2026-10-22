from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func

from app.db.database import Base


class DonorMatch(Base):
    __tablename__ = "donor_matches"
    __table_args__ = (
        UniqueConstraint("request_id", "donor_id", name="uq_donor_matches_request_donor"),
    )

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("blood_requests.id"), nullable=False, index=True)
    donor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    compatibility_type = Column(String, nullable=False)
    distance_km = Column(Float, nullable=True)
    match_score = Column(Float, nullable=False, default=0.0)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
