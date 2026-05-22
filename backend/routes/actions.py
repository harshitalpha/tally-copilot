import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
import models
from auth import get_current_user

router = APIRouter()


def _serialize(action: models.UserAction) -> dict:
    try:
        data = json.loads(action.data)
    except (TypeError, ValueError):
        data = {}
    return {
        "id": action.id,
        "action_type": action.action_type,
        "status": action.status,
        "data": data,
        "created_at": action.created_at.isoformat() if action.created_at else None,
        "updated_at": action.updated_at.isoformat() if action.updated_at else None,
    }


@router.get("")
def list_actions(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    q = db.query(models.UserAction).filter(models.UserAction.user_id == current_user.id)
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if statuses:
            q = q.filter(models.UserAction.status.in_(statuses))
    total = q.count()
    items = q.order_by(models.UserAction.created_at.desc()).offset(offset).limit(limit).all()
    return {"total": total, "items": [_serialize(a) for a in items]}


@router.get("/{action_id}")
def get_action(
    action_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    action = (
        db.query(models.UserAction)
        .filter(
            models.UserAction.id == action_id,
            models.UserAction.user_id == current_user.id,
        )
        .first()
    )
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return _serialize(action)
