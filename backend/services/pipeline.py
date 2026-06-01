import json
from datetime import datetime
from database import SessionLocal
from models import UserAction, Document, UserSettings
from services.extractor import extract_and_classify
from services.validator import validate
from services import whatsapp_sender


def run_pipeline(action_id: str):
    db = SessionLocal()
    try:
        action = db.query(UserAction).filter(UserAction.id == action_id).first()
        if not action:
            return

        action.status = "processing"
        action.updated_at = datetime.utcnow()
        db.commit()

        data = json.loads(action.data)
        doc = db.query(Document).filter(Document.id == data["document_id"]).first()

        # Stage 1+2: extract text/image + LLM classify/extract
        extracted, method = extract_and_classify(
            file_path=doc.file_path,
            file_type=doc.file_type,
            user_id=action.user_id,
        )
        doc.raw_text = extracted.get("_raw_text", "")
        doc.extraction_method = method
        db.commit()

        # Stage 3: validate
        validation = validate(extracted)

        # Stage 4: store results
        data["extracted_invoice"] = extracted
        data["validation_errors"]   = validation["errors"]
        data["validation_warnings"] = validation["warnings"]
        data["extraction_method"]   = method
        action.data = json.dumps(data)
        db.commit()

        if validation["errors"]:
            summary = "; ".join(validation["errors"][:3])
            _fail(db, action_id, summary)
            return

        # Stage 5: route to pending_review or pending_sync
        settings = db.query(UserSettings).filter(
            UserSettings.user_id == action.user_id
        ).first()

        if settings and settings.require_review_before_tally:
            action.status = "pending_review"
        else:
            action.status = "pending_sync"
        action.updated_at = datetime.utcnow()
        db.commit()

    except json.JSONDecodeError as e:
        _fail(db, action_id, f"LLM returned invalid JSON: {e}")
    except Exception as e:
        _fail(db, action_id, f"Pipeline error: {e}")
    finally:
        db.close()


def _fail(db, action_id: str, error: str):
    action = db.query(UserAction).filter(UserAction.id == action_id).first()
    if not action:
        return
    try:
        d = json.loads(action.data)
    except (TypeError, ValueError):
        d = {}
    d["tally_error"] = error
    action.data = json.dumps(d)
    action.status = "failed"
    action.updated_at = datetime.utcnow()
    db.commit()

    from models import UserWhatsappMetadata
    wa = db.query(UserWhatsappMetadata).filter(
        UserWhatsappMetadata.user_id == action.user_id,
        UserWhatsappMetadata.is_verified == True,
    ).first()
    if wa:
        sender_phone = d.get("sender_phone") or wa.phone_number
        whatsapp_sender.send_failure(sender_phone, error)
