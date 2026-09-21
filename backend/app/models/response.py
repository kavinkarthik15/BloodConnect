from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.db.database import Base


class DonorResponse(Base):
    __tablename__ = "donor_responses"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, nullable=False, index=True)
    donor_id = Column(Integer, nullable=False, index=True)
    response = Column(String, nullable=False)
    responded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    notes = Column(Text, nullable=True)
