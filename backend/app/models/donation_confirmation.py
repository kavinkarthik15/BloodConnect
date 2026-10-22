from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func

from app.db.database import Base


class DonationConfirmation(Base):
    __tablename__ = "donation_confirmations"
    __table_args__ = (
        CheckConstraint("units_confirmed > 0", name="ck_donation_confirmations_units_positive"),
        UniqueConstraint("request_id", "donor_id", name="uq_donation_confirmations_request_donor"),
    )

    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey("blood_requests.id"), nullable=False, index=True)
    donor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    confirmed_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    units_confirmed = Column(Integer, nullable=False)
    verification_source = Column(String, nullable=False)
    reference = Column(String(120), nullable=True)
    notes = Column(Text, nullable=True)
    confirmed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
