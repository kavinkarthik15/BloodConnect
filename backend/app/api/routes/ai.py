from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.database import get_db
from app.models.user import User
from app.services.ai_service import AIService

router = APIRouter(prefix="/api/assistant", tags=["ai"])
legacy_router = APIRouter(prefix="/api/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
async def chat(payload: ChatRequest, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    return AIService.generate_chat_response(user, db, payload.message)


@legacy_router.post("/chat")
async def legacy_chat(payload: ChatRequest, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    return AIService.generate_chat_response(user, db, payload.message)
