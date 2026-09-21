from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    type: str
    title: str
    message: str
    related_entity_id: int | None = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True
