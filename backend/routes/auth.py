from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
import models
from auth import hash_password, verify_password, create_token, get_current_user

router = APIRouter()


class SignupRequest(BaseModel):
    first_name: str
    last_name: str | None = None
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def _serialize_user_basic(user: models.User) -> dict:
    return {
        "id": user.id,
        "first_name": user.first_name,
        "email": user.email,
        "is_onboarded": user.is_onboarded,
    }


@router.post("/signup", status_code=201)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        first_name=body.first_name,
        last_name=body.last_name,
        email=body.email,
        password_hash=hash_password(body.password),
        is_onboarded=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(user.id)
    return {"token": token, "user": _serialize_user_basic(user)}


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(user.id)
    return {"token": token, "user": _serialize_user_basic(user)}


@router.get("/me")
def me(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    wa = db.query(models.UserWhatsappMetadata).filter(
        models.UserWhatsappMetadata.user_id == current_user.id
    ).first()
    tally = db.query(models.UserTallyMetadata).filter(
        models.UserTallyMetadata.user_id == current_user.id
    ).first()

    connector_online = False
    if tally and tally.last_heartbeat_at:
        delta = (datetime.utcnow() - tally.last_heartbeat_at).total_seconds()
        connector_online = delta < 90

    return {
        "id": current_user.id,
        "first_name": current_user.first_name,
        "email": current_user.email,
        "is_onboarded": current_user.is_onboarded,
        "whatsapp": (
            {
                "phone_number": wa.phone_number,
                "is_verified": wa.is_verified,
            }
            if wa
            else None
        ),
        "tally": (
            {
                "is_paired": tally.is_paired,
                "company_name": tally.company_name,
                "connector_online": connector_online,
            }
            if tally
            else None
        ),
    }
