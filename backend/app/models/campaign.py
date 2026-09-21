from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.db.database import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String, nullable=False)
    campaign_date = Column(DateTime(timezone=True), nullable=False)
    organizer_id = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="planned")
    participant_count = Column(Integer, default=0)
    registered_donors = Column(Integer, default=0)
    units_recorded = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
