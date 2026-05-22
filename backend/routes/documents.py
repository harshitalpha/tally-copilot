import json, uuid, pathlib, mimetypes
from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
import models
from auth import get_current_user
from services.pipeline import run_pipeline

router = APIRouter()

UPLOADS_DIR = pathlib.Path(__file__).resolve().parent.parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTS = {"pdf", "jpg", "jpeg", "png", "heic"}


@router.post("/upload", status_code=201)
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source: str = Form("dashboard"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    original_name = file.filename or "upload"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else "bin"
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    stored = f"{uuid.uuid4()}.{ext}"
    path = UPLOADS_DIR / stored
    contents = await file.read()
    path.write_bytes(contents)

    doc = models.Document(
        user_id=current_user.id,
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
        user_id=current_user.id,
        action_type="UPLOAD_INVOICE_TO_TALLY",
        status="pending",
        data=json.dumps(
            {
                "document_id": doc.id,
                "source": source,
                "sender_phone": None,
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

    return {"document_id": doc.id, "action_id": action.id, "status": "pending"}


@router.get("/{document_id}/file")
def get_file(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc = (
        db.query(models.Document)
        .filter(models.Document.id == document_id, models.Document.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    path = pathlib.Path(doc.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")

    media_type = mimetypes.guess_type(str(path))[0]
    if not media_type:
        if doc.file_type == "pdf":
            media_type = "application/pdf"
        elif doc.file_type in ("jpg", "jpeg"):
            media_type = "image/jpeg"
        elif doc.file_type == "png":
            media_type = "image/png"
        else:
            media_type = "application/octet-stream"

    return FileResponse(path, media_type=media_type, filename=doc.original_filename or doc.stored_filename)
