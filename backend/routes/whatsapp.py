import os, json, uuid, pathlib, httpx
from fastapi import APIRouter, Request, BackgroundTasks, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
import models
from services import whatsapp_sender
from services.pipeline import run_pipeline

router = APIRouter()

UPLOADS_DIR = pathlib.Path(os.getenv("UPLOAD_DIR") or (pathlib.Path(__file__).resolve().parent.parent / "uploads"))
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/webhook")
def verify_webhook(request: Request):
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == os.getenv("WHATSAPP_VERIFY_TOKEN")
    ):
        return PlainTextResponse(params.get("hub.challenge", ""))
    raise HTTPException(status_code=403, detail="Verification failed")


def _extract_message(payload: dict) -> dict | None:
    try:
        entry = (payload.get("entry") or [])[0]
        change = (entry.get("changes") or [])[0]
        messages = (change.get("value") or {}).get("messages") or []
        if not messages:
            return None
        msg = messages[0]
        out = {"from": msg.get("from"), "type": msg.get("type")}
        if msg.get("type") == "document":
            d = msg.get("document") or {}
            out["media_id"] = d.get("id")
            out["mime_type"] = d.get("mime_type")
            out["filename"] = d.get("filename")
        elif msg.get("type") == "image":
            d = msg.get("image") or {}
            out["media_id"] = d.get("id")
            out["mime_type"] = d.get("mime_type")
        return out
    except (IndexError, AttributeError, KeyError):
        return None


def _download_media(media_id: str, dest: pathlib.Path):
    """Download media from Meta Graph API. Stubbed for dev — real impl in production."""
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    if not token:
        return False
    try:
        meta_url = f"https://graph.facebook.com/v18.0/{media_id}"
        with httpx.Client(timeout=20) as client:
            r = client.get(meta_url, headers={"Authorization": f"Bearer {token}"})
            r.raise_for_status()
            url = r.json().get("url")
            if not url:
                return False
            r2 = client.get(url, headers={"Authorization": f"Bearer {token}"})
            r2.raise_for_status()
            dest.write_bytes(r2.content)
            return True
    except Exception:
        return False


def handle_incoming_invoice(user_id: str, message: dict, sender_phone: str):
    db = SessionLocal()
    try:
        media_id = message.get("media_id")
        mime = (message.get("mime_type") or "").lower()
        if "pdf" in mime:
            ext = "pdf"
        elif "jpeg" in mime or "jpg" in mime:
            ext = "jpg"
        elif "png" in mime:
            ext = "png"
        elif "heic" in mime:
            ext = "heic"
        else:
            ext = "bin"

        stored = f"{uuid.uuid4()}.{ext}"
        path = UPLOADS_DIR / stored

        ok = _download_media(media_id, path) if media_id else False
        if not ok:
            whatsapp_sender.send_failure(
                sender_phone, "Could not download your file. Please resend."
            )
            return

        doc = models.Document(
            user_id=user_id,
            original_filename=message.get("filename"),
            stored_filename=stored,
            file_path=str(path),
            file_type=ext,
            file_size_bytes=path.stat().st_size if path.exists() else None,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        action = models.UserAction(
            user_id=user_id,
            action_type="UPLOAD_INVOICE_TO_TALLY",
            status="pending",
            data=json.dumps(
                {
                    "document_id": doc.id,
                    "source": "whatsapp",
                    "sender_phone": sender_phone,
                    "extracted_invoice": None,
                    "validation_errors": [],
                    "validation_warnings": [],
                    "tally_voucher_id": None,
                    "tally_error": None,
                }
            ),
        )
        db.add(action)
        db.commit()
        db.refresh(action)

        action_id = action.id
    finally:
        db.close()

    run_pipeline(action_id)


@router.post("/webhook")
async def webhook(
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    message = _extract_message(payload)
    if not message:
        return {"status": "ok"}

    sender_phone = message["from"]

    wa_meta = (
        db.query(models.UserWhatsappMetadata)
        .filter(
            models.UserWhatsappMetadata.phone_number == sender_phone,
            models.UserWhatsappMetadata.is_verified == True,
        )
        .first()
    )

    if not wa_meta:
        background_tasks.add_task(
            whatsapp_sender.send_text,
            sender_phone,
            "You are not registered. Please sign up at app.yourproduct.com",
            "unregistered",
        )
        return {"status": "ok"}

    if message["type"] not in ("document", "image"):
        return {"status": "ok"}

    background_tasks.add_task(
        handle_incoming_invoice,
        user_id=wa_meta.user_id,
        message=message,
        sender_phone=sender_phone,
    )
    return {"status": "ok"}
