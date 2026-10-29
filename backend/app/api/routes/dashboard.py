from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import DashboardStatus
from app.services.bot_service import build_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/status", response_model=DashboardStatus)
def status(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return build_dashboard(db, user)
