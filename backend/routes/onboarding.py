import json, random, string
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
import models
from auth import get_current_user

router = APIRouter()


# ============ WhatsApp ============

class WAConnectRequest(BaseModel):
    phone_number: str


class WAVerifyRequest(BaseModel):
    otp: str


@router.post("/whatsapp/connect")
def whatsapp_connect(
    body: WAConnectRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    phone = body.phone_number.strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number required")

    otp = "".join(random.choices(string.digits, k=6))
    expires = datetime.utcnow() + timedelta(minutes=10)

    wa = (
        db.query(models.UserWhatsappMetadata)
        .filter(models.UserWhatsappMetadata.user_id == current_user.id)
        .first()
    )
    if wa:
        wa.phone_number = phone
        wa.otp_code = otp
        wa.otp_expires_at = expires
        wa.is_verified = False
    else:
        wa = models.UserWhatsappMetadata(
            user_id=current_user.id,
            phone_number=phone,
            otp_code=otp,
            otp_expires_at=expires,
            is_verified=False,
        )
        db.add(wa)
    db.commit()

    import os
    response = {"message": "OTP sent"}
    if os.getenv("APP_ENV") == "development":
        response["dev_otp"] = otp
    return response


@router.post("/whatsapp/verify")
def whatsapp_verify(
    body: WAVerifyRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    wa = (
        db.query(models.UserWhatsappMetadata)
        .filter(models.UserWhatsappMetadata.user_id == current_user.id)
        .first()
    )
    if not wa or not wa.otp_code:
        raise HTTPException(status_code=400, detail="No pending OTP")
    if wa.otp_expires_at and wa.otp_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    if body.otp.strip() != wa.otp_code:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    wa.is_verified = True
    wa.verified_at = datetime.utcnow()
    wa.otp_code = None
    wa.otp_expires_at = None
    db.commit()

    _maybe_mark_onboarded(db, current_user)
    return {"verified": True, "phone_number": wa.phone_number}


# ============ Tally ============

class SelectCompanyRequest(BaseModel):
    company_name: str


class SaveMappingsRequest(BaseModel):
    purchase_ledger: str
    cgst_ledger_format: str
    sgst_ledger_format: str
    igst_ledger_format: str
    auto_create_ledgers: bool = True


def _gen_pairing_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def _get_or_create_tally(db: Session, user_id: str) -> models.UserTallyMetadata:
    tally = (
        db.query(models.UserTallyMetadata)
        .filter(models.UserTallyMetadata.user_id == user_id)
        .first()
    )
    if not tally:
        tally = models.UserTallyMetadata(user_id=user_id)
        db.add(tally)
        db.commit()
        db.refresh(tally)
    return tally


@router.post("/tally/generate-pairing-code")
def generate_pairing_code(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tally = _get_or_create_tally(db, current_user.id)
    tally.pairing_code = _gen_pairing_code()
    tally.pairing_code_expires_at = datetime.utcnow() + timedelta(minutes=10)
    tally.is_paired = False
    tally.connector_token = None
    db.commit()
    return {"pairing_code": tally.pairing_code, "expires_in_seconds": 600}


@router.get("/tally/pairing-status")
def pairing_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tally = (
        db.query(models.UserTallyMetadata)
        .filter(models.UserTallyMetadata.user_id == current_user.id)
        .first()
    )
    if not tally:
        return {"is_paired": False, "pairing_code": None, "expires_in_seconds": 0}

    if tally.is_paired:
        companies = []
        if tally.available_ledgers is None and tally.company_name:
            companies = [tally.company_name]
        try:
            stored = json.loads(tally.available_ledgers) if tally.available_ledgers else {}
            if isinstance(stored, dict) and stored.get("companies"):
                companies = stored["companies"]
        except (TypeError, ValueError):
            pass
        if not companies and tally.company_name:
            companies = [tally.company_name]
        return {"is_paired": True, "company_names": companies}

    expires_in = 0
    if tally.pairing_code_expires_at:
        expires_in = max(
            0, int((tally.pairing_code_expires_at - datetime.utcnow()).total_seconds())
        )
    return {
        "is_paired": False,
        "pairing_code": tally.pairing_code,
        "expires_in_seconds": expires_in,
    }


@router.post("/tally/select-company")
def select_company(
    body: SelectCompanyRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tally = (
        db.query(models.UserTallyMetadata)
        .filter(models.UserTallyMetadata.user_id == current_user.id)
        .first()
    )
    if not tally or not tally.is_paired:
        raise HTTPException(status_code=400, detail="Connector not paired")
    tally.company_name = body.company_name.strip()
    db.commit()
    return {"message": "Company selected"}


@router.get("/tally/ledgers")
def get_ledgers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tally = (
        db.query(models.UserTallyMetadata)
        .filter(models.UserTallyMetadata.user_id == current_user.id)
        .first()
    )
    ledgers = []
    if tally and tally.available_ledgers:
        try:
            parsed = json.loads(tally.available_ledgers)
            if isinstance(parsed, dict):
                ledgers = parsed.get("ledgers", [])
            elif isinstance(parsed, list):
                ledgers = parsed
        except (TypeError, ValueError):
            ledgers = []
    return {"ledgers": ledgers}


@router.post("/tally/save-mappings")
def save_mappings(
    body: SaveMappingsRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tally = (
        db.query(models.UserTallyMetadata)
        .filter(models.UserTallyMetadata.user_id == current_user.id)
        .first()
    )
    if not tally:
        raise HTTPException(status_code=400, detail="No Tally metadata; complete pairing first")

    tally.purchase_ledger = body.purchase_ledger
    tally.cgst_ledger_format = body.cgst_ledger_format
    tally.sgst_ledger_format = body.sgst_ledger_format
    tally.igst_ledger_format = body.igst_ledger_format
    tally.auto_create_ledgers = body.auto_create_ledgers
    db.commit()

    _maybe_mark_onboarded(db, current_user)
    return {"message": "Setup complete", "is_onboarded": current_user.is_onboarded}


def _maybe_mark_onboarded(db: Session, user: models.User):
    wa = (
        db.query(models.UserWhatsappMetadata)
        .filter(
            models.UserWhatsappMetadata.user_id == user.id,
            models.UserWhatsappMetadata.is_verified == True,
        )
        .first()
    )
    tally = (
        db.query(models.UserTallyMetadata)
        .filter(
            models.UserTallyMetadata.user_id == user.id,
            models.UserTallyMetadata.is_paired == True,
        )
        .first()
    )
    if wa and tally and tally.company_name and tally.purchase_ledger:
        user.is_onboarded = True
        db.commit()
