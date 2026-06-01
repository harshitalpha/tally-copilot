"""User settings — Tally mappings, review mode, WhatsApp number."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from database import get_db
import models
from auth import get_current_user

router = APIRouter()


class TallySettingsRequest(BaseModel):
    purchase_ledger:    str
    cgst_ledger_format: str
    sgst_ledger_format: str
    igst_ledger_format: str
    auto_create_ledgers: bool = True


class ReviewModeRequest(BaseModel):
    require_review: bool


class WhatsAppConnectRequest(BaseModel):
    phone_number: str


@router.get("")
def get_settings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tally = db.query(models.UserTallyMetadata).filter(
        models.UserTallyMetadata.user_id == current_user.id
    ).first()
    wa = db.query(models.UserWhatsappMetadata).filter(
        models.UserWhatsappMetadata.user_id == current_user.id
    ).first()
    settings = db.query(models.UserSettings).filter(
        models.UserSettings.user_id == current_user.id
    ).first()

    return {
        "tally": {
            "purchase_ledger":    tally.purchase_ledger    if tally else "Purchases",
            "cgst_ledger_format": tally.cgst_ledger_format if tally else "CGST @ {rate}%",
            "sgst_ledger_format": tally.sgst_ledger_format if tally else "SGST @ {rate}%",
            "igst_ledger_format": tally.igst_ledger_format if tally else "IGST @ {rate}%",
            "auto_create_ledgers": tally.auto_create_ledgers if tally else True,
            "company_name": tally.company_name if tally else None,
        } if tally else None,
        "whatsapp": {
            "phone_number": wa.phone_number,
            "is_verified":  wa.is_verified,
        } if wa else None,
        "require_review_before_tally": settings.require_review_before_tally if settings else False,
    }


@router.put("/tally")
def update_tally_settings(
    body: TallySettingsRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tally = db.query(models.UserTallyMetadata).filter(
        models.UserTallyMetadata.user_id == current_user.id
    ).first()
    if not tally:
        raise HTTPException(400, "Tally not connected yet")
    tally.purchase_ledger    = body.purchase_ledger
    tally.cgst_ledger_format = body.cgst_ledger_format
    tally.sgst_ledger_format = body.sgst_ledger_format
    tally.igst_ledger_format = body.igst_ledger_format
    tally.auto_create_ledgers = body.auto_create_ledgers
    db.commit()
    return {"message": "Tally settings updated"}


@router.put("/review-mode")
def update_review_mode(
    body: ReviewModeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    settings = db.query(models.UserSettings).filter(
        models.UserSettings.user_id == current_user.id
    ).first()
    if not settings:
        settings = models.UserSettings(user_id=current_user.id)
        db.add(settings)
    settings.require_review_before_tally = body.require_review
    db.commit()
    return {"require_review_before_tally": settings.require_review_before_tally}


@router.post("/whatsapp/connect")
def whatsapp_connect(
    body: WhatsAppConnectRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Add or update WhatsApp number from Settings (post-onboarding)."""
    import random, string, os
    from datetime import timedelta
    phone = body.phone_number.strip()
    otp   = "".join(random.choices(string.digits, k=6))
    expires = datetime.utcnow() + timedelta(minutes=10)

    wa = db.query(models.UserWhatsappMetadata).filter(
        models.UserWhatsappMetadata.user_id == current_user.id
    ).first()
    if wa:
        wa.phone_number = phone; wa.otp_code = otp
        wa.otp_expires_at = expires; wa.is_verified = False
    else:
        wa = models.UserWhatsappMetadata(
            user_id=current_user.id, phone_number=phone,
            otp_code=otp, otp_expires_at=expires, is_verified=False,
        )
        db.add(wa)
    db.commit()

    # In production: send OTP via WhatsApp/SMS
    resp: dict = {"message": "OTP sent to your WhatsApp"}
    if os.getenv("APP_ENV") == "development":
        resp["dev_otp"] = otp
    return resp


@router.post("/whatsapp/verify")
def whatsapp_verify(
    body: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    otp = (body.get("otp") or "").strip()
    wa  = db.query(models.UserWhatsappMetadata).filter(
        models.UserWhatsappMetadata.user_id == current_user.id
    ).first()
    if not wa or not wa.otp_code:
        raise HTTPException(400, "No pending OTP")
    if wa.otp_expires_at and wa.otp_expires_at < datetime.utcnow():
        raise HTTPException(400, "OTP expired")
    if otp != wa.otp_code:
        raise HTTPException(400, "Invalid OTP")
    wa.is_verified = True; wa.verified_at = datetime.utcnow()
    wa.otp_code = None; wa.otp_expires_at = None
    db.commit()
    return {"verified": True, "phone_number": wa.phone_number}
