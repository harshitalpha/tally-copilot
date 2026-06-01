import os, json, uuid, pathlib
from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from database import get_db
import models
from services import whatsapp_sender
from services.pipeline import run_pipeline

router = APIRouter()

UPLOADS_DIR = pathlib.Path(os.getenv("UPLOAD_DIR") or (pathlib.Path(__file__).resolve().parent.parent / "uploads"))
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/whatsapp/incoming")
async def mock_incoming(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    sender_phone: str = Form(...),
    db: Session = Depends(get_db),
):
    wa = (
        db.query(models.UserWhatsappMetadata)
        .filter(
            models.UserWhatsappMetadata.phone_number == sender_phone,
            models.UserWhatsappMetadata.is_verified == True,
        )
        .first()
    )
    if not wa:
        whatsapp_sender.send_text(
            sender_phone,
            "You are not registered. Please sign up at app.yourproduct.com",
            "unregistered",
        )
        return {
            "result": "not_registered",
            "message": f"Phone {sender_phone} not found in user_whatsapp_metadata",
        }

    original_name = file.filename or "upload"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else "bin"
    stored = f"{uuid.uuid4()}.{ext}"
    path = UPLOADS_DIR / stored
    contents = await file.read()
    path.write_bytes(contents)

    doc = models.Document(
        user_id=wa.user_id,
        original_filename=original_name,
        stored_filename=stored,
        file_path=str(path),
        file_type=ext,
        file_size_bytes=len(contents),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    action = models.UserAction(
        user_id=wa.user_id,
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

    background_tasks.add_task(run_pipeline, action.id)

    return {"result": "processing", "action_id": action.id}


@router.post("/tally/voucher")
async def mock_tally_voucher(request: Request):
    _ = await request.body()
    xml = (
        "<RESPONSE>"
        "<CREATED>1</CREATED>"
        "<ALTERED>0</ALTERED>"
        "<ERRORS>0</ERRORS>"
        f"<LASTVCHID>{99000 + (hash(str(request.url)) % 1000)}</LASTVCHID>"
        "</RESPONSE>"
    )
    return Response(content=xml, media_type="application/xml")


@router.get("/whatsapp/send-log")
def send_log():
    return whatsapp_sender.get_send_log()
