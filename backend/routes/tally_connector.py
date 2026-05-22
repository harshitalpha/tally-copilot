import json, secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
import models
from auth import get_connector_user
from services import whatsapp_sender

router = APIRouter()


class PairRequest(BaseModel):
    pairing_code: str
    company_names: List[str] = []


class LedgerEntry(BaseModel):
    name: str
    group: Optional[str] = None


class LedgersRequest(BaseModel):
    ledgers: List[LedgerEntry]


class SyncCompleteRequest(BaseModel):
    voucher_id: str = ""


class SyncFailedRequest(BaseModel):
    error: str = "Unknown error"


@router.post("/pair")
def pair(body: PairRequest, db: Session = Depends(get_db)):
    code = body.pairing_code.strip().upper()
    tally = (
        db.query(models.UserTallyMetadata)
        .filter(models.UserTallyMetadata.pairing_code == code)
        .first()
    )
    if not tally:
        raise HTTPException(status_code=400, detail="Invalid or expired pairing code")
    if tally.pairing_code_expires_at and tally.pairing_code_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired pairing code")

    token = secrets.token_hex(32)
    tally.connector_token = token
    tally.is_paired = True
    tally.paired_at = datetime.utcnow()
    tally.pairing_code = None
    tally.pairing_code_expires_at = None
    tally.last_heartbeat_at = datetime.utcnow()

    existing = {}
    if tally.available_ledgers:
        try:
            existing = json.loads(tally.available_ledgers)
            if not isinstance(existing, dict):
                existing = {}
        except (TypeError, ValueError):
            existing = {}
    existing["companies"] = body.company_names
    tally.available_ledgers = json.dumps(existing)

    if body.company_names and not tally.company_name:
        if len(body.company_names) == 1:
            tally.company_name = body.company_names[0]

    db.commit()
    return {"connector_token": token, "message": "Paired"}


@router.post("/heartbeat")
def heartbeat(
    db: Session = Depends(get_db),
    connector_user: models.User = Depends(get_connector_user),
):
    tally = (
        db.query(models.UserTallyMetadata)
        .filter(models.UserTallyMetadata.user_id == connector_user.id)
        .first()
    )
    prev_updated = tally.updated_at
    tally.last_heartbeat_at = datetime.utcnow()
    db.commit()
    config_updated = False
    return {"ok": True, "config_updated": config_updated}


@router.get("/config")
def get_config(
    db: Session = Depends(get_db),
    connector_user: models.User = Depends(get_connector_user),
):
    tally = (
        db.query(models.UserTallyMetadata)
        .filter(models.UserTallyMetadata.user_id == connector_user.id)
        .first()
    )
    return {
        "company_name": tally.company_name,
        "purchase_ledger": tally.purchase_ledger or "Purchases",
        "cgst_ledger_format": tally.cgst_ledger_format or "CGST @ {rate}%",
        "sgst_ledger_format": tally.sgst_ledger_format or "SGST @ {rate}%",
        "igst_ledger_format": tally.igst_ledger_format or "IGST @ {rate}%",
        "auto_create_ledgers": bool(tally.auto_create_ledgers),
    }


@router.post("/ledgers")
def post_ledgers(
    body: LedgersRequest,
    db: Session = Depends(get_db),
    connector_user: models.User = Depends(get_connector_user),
):
    tally = (
        db.query(models.UserTallyMetadata)
        .filter(models.UserTallyMetadata.user_id == connector_user.id)
        .first()
    )
    existing = {}
    if tally.available_ledgers:
        try:
            existing = json.loads(tally.available_ledgers)
            if not isinstance(existing, dict):
                existing = {}
        except (TypeError, ValueError):
            existing = {}
    existing["ledgers"] = [l.model_dump() for l in body.ledgers]
    tally.available_ledgers = json.dumps(existing)
    db.commit()
    return {"stored": len(body.ledgers)}


@router.get("/actions/pending-sync")
def pending_sync(
    db: Session = Depends(get_db),
    connector_user: models.User = Depends(get_connector_user),
):
    actions = (
        db.query(models.UserAction)
        .filter(
            models.UserAction.user_id == connector_user.id,
            models.UserAction.status == "pending_sync",
        )
        .order_by(models.UserAction.created_at.asc())
        .all()
    )
    out = []
    for a in actions:
        try:
            data = json.loads(a.data)
        except (TypeError, ValueError):
            data = {}
        out.append({"id": a.id, "data": data})
    return out


@router.post("/actions/{action_id}/sync-complete")
def sync_complete(
    action_id: str,
    body: SyncCompleteRequest,
    db: Session = Depends(get_db),
    connector_user: models.User = Depends(get_connector_user),
):
    action = (
        db.query(models.UserAction)
        .filter(
            models.UserAction.id == action_id,
            models.UserAction.user_id == connector_user.id,
        )
        .first()
    )
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    try:
        d = json.loads(action.data)
    except (TypeError, ValueError):
        d = {}
    d["tally_voucher_id"] = body.voucher_id
    action.data = json.dumps(d)
    action.status = "synced"
    db.commit()

    wa = (
        db.query(models.UserWhatsappMetadata)
        .filter(
            models.UserWhatsappMetadata.user_id == action.user_id,
            models.UserWhatsappMetadata.is_verified == True,
        )
        .first()
    )
    if wa:
        inv = d.get("extracted_invoice") or {}
        sender_phone = d.get("sender_phone") or wa.phone_number
        whatsapp_sender.send_confirmation(
            phone=sender_phone,
            supplier=inv.get("supplier_name") or "Unknown",
            amount=inv.get("total_amount") or 0,
            voucher_id=body.voucher_id,
        )
    return {"status": "synced"}


@router.post("/actions/{action_id}/sync-failed")
def sync_failed(
    action_id: str,
    body: SyncFailedRequest,
    db: Session = Depends(get_db),
    connector_user: models.User = Depends(get_connector_user),
):
    action = (
        db.query(models.UserAction)
        .filter(
            models.UserAction.id == action_id,
            models.UserAction.user_id == connector_user.id,
        )
        .first()
    )
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    try:
        d = json.loads(action.data)
    except (TypeError, ValueError):
        d = {}
    d["tally_error"] = body.error
    action.data = json.dumps(d)
    action.status = "failed"
    db.commit()

    wa = (
        db.query(models.UserWhatsappMetadata)
        .filter(
            models.UserWhatsappMetadata.user_id == action.user_id,
            models.UserWhatsappMetadata.is_verified == True,
        )
        .first()
    )
    if wa:
        sender_phone = d.get("sender_phone") or wa.phone_number
        whatsapp_sender.send_failure(phone=sender_phone, error=body.error)
    return {"status": "failed"}
