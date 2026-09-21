from datetime import datetime

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.response import DonorResponse


class NotificationService:
    @staticmethod
    def create(db: Session, user_id: int, notification_type: str, title: str, message: str, related_entity_id: int | None = None):
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            related_entity_id=related_entity_id,
            is_read=False,
            created_at=datetime.utcnow(),
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def get_for_user(db: Session, user_id: int, limit: int = 100):
        return db.query(Notification).filter(Notification.user_id == user_id).order_by(Notification.created_at.desc()).limit(limit).all()

    @staticmethod
    def unread_count(db: Session, user_id: int):
        return db.query(Notification).filter(Notification.user_id == user_id, Notification.is_read.is_(False)).count()

    @staticmethod
    def mark_read(db: Session, notification_id: int, user_id: int):
        notification = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == user_id).first()
        if notification:
            notification.is_read = True
            db.commit()
        return notification

    @staticmethod
    def mark_all_read(db: Session, user_id: int):
        db.query(Notification).filter(Notification.user_id == user_id, Notification.is_read.is_(False)).update({"is_read": True})
        db.commit()

    @staticmethod
    def record_response(db: Session, request_id: int, donor_id: int, response: str):
        existing = db.query(DonorResponse).filter(DonorResponse.request_id == request_id, DonorResponse.donor_id == donor_id).first()
        if existing:
            return existing
        item = DonorResponse(request_id=request_id, donor_id=donor_id, response=response)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item
