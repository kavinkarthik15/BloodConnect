from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func

from app.db.database import Base


class DonorResponse(Base):
    __tablename__ = "donor_responses"
    __table_args__ = (
        UniqueConstraint("request_id", "donor_id", name="uq_donor_responses_request_donor"),
    )

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("blood_requests.id"), nullable=False, index=True)
    donor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    response = Column(String, nullable=False)
    responded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    notes = Column(Text, nullable=True)
