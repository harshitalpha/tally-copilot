import random, string, secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db
import models
from auth import hash_password, verify_password, create_token, get_current_user
from services import email_sender

router = APIRouter()


class SignupRequest(BaseModel):
    first_name: str
    last_name: str | None = None
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyEmailRequest(BaseModel):
    otp: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


def _otp() -> str:
    return "".join(random.choices(string.digits, k=6))


def _serialize_user(user: models.User) -> dict:
    return {
        "id": user.id,
        "first_name": user.first_name,
        "email": user.email,
        "is_onboarded": user.is_onboarded,
        "email_verified": user.email_verified,
    }


@router.post("/signup", status_code=201)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    otp = _otp()
    user = models.User(
        first_name=body.first_name,
        last_name=body.last_name,
        email=body.email,
        password_hash=hash_password(body.password),
        is_onboarded=False,
        email_verified=False,
        email_otp=otp,
        email_otp_expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    email_sender.send_otp(user.email, otp, purpose="verification")

    import os
    token = create_token(user.id)
    response: dict = {"token": token, "user": _serialize_user(user)}
    if os.getenv("APP_ENV") == "development":
        response["dev_otp"] = otp
    return response


@router.post("/verify-email")
def verify_email(
    body: VerifyEmailRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.email_verified:
        return {"verified": True}
    if not current_user.email_otp:
        raise HTTPException(400, "No pending OTP")
    if current_user.email_otp_expires_at and current_user.email_otp_expires_at < datetime.utcnow():
        raise HTTPException(400, "OTP expired — request a new one")
    if body.otp.strip() != current_user.email_otp:
        raise HTTPException(400, "Invalid OTP")

    current_user.email_verified = True
    current_user.email_otp = None
    current_user.email_otp_expires_at = None
    db.commit()
    return {"verified": True}


@router.post("/resend-otp")
def resend_otp(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.email_verified:
        return {"message": "Already verified"}
    otp = _otp()
    current_user.email_otp = otp
    current_user.email_otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
    db.commit()
    email_sender.send_otp(current_user.email, otp, purpose="verification")
    import os
    resp: dict = {"message": "OTP sent"}
    if os.getenv("APP_ENV") == "development":
        resp["dev_otp"] = otp
    return resp


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": create_token(user.id), "user": _serialize_user(user)}


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
        connector_online = (datetime.utcnow() - tally.last_heartbeat_at).total_seconds() < 90
    return {
        "id": current_user.id,
        "first_name": current_user.first_name,
        "email": current_user.email,
        "is_onboarded": current_user.is_onboarded,
        "email_verified": current_user.email_verified,
        "whatsapp": ({"phone_number": wa.phone_number, "is_verified": wa.is_verified} if wa else None),
        "tally": ({"is_paired": tally.is_paired, "company_name": tally.company_name,
                   "connector_online": connector_online} if tally else None),
    }


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email).first()
    if user:
        token = secrets.token_urlsafe(32)
        user.password_reset_token = token
        user.password_reset_expires_at = datetime.utcnow() + timedelta(hours=1)
        db.commit()
        import os
        app_url = os.getenv("APP_URL", "http://localhost:5173")
        reset_url = f"{app_url}/reset-password?token={token}"
        email_sender.send_password_reset(user.email, reset_url)
        if os.getenv("APP_ENV") == "development":
            return {"message": "Reset link sent.", "dev_reset_url": reset_url}
    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.password_reset_token == body.token
    ).first()
    if not user:
        raise HTTPException(400, "Invalid or expired reset link")
    if user.password_reset_expires_at and user.password_reset_expires_at < datetime.utcnow():
        raise HTTPException(400, "Reset link has expired — request a new one")

    user.password_hash = hash_password(body.new_password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    db.commit()
    return {"message": "Password updated — please sign in"}
