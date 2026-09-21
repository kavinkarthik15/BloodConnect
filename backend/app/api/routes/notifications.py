from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.notification import NotificationResponse
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    return NotificationService.get_for_user(db, user.id, limit=100)


@router.get("/unread-count")
async def unread_count(user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    return {"count": NotificationService.unread_count(db, user.id)}


@router.patch("/{notification_id}/read")
async def mark_read(notification_id: int, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    notification = NotificationService.mark_read(db, notification_id, user.id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return {"message": "Marked as read."}


@router.patch("/read-all")
async def mark_all_read(user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    NotificationService.mark_all_read(db, user.id)
    return {"message": "All notifications marked as read."}
