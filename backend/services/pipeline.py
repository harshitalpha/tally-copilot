import json
from datetime import datetime
from database import SessionLocal
from models import UserAction, Document
from services.extractor import extract_text, llm_extract
from services.validator import validate
from services import whatsapp_sender


def run_pipeline(action_id: str):
    """
    Full pipeline: extract -> validate -> mark pending_sync.
    WhatsApp confirmation is sent AFTER the connector reports sync result,
    not here. Failure notifications ARE sent here if extraction fails.
    """
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

        # Stage 1: extract text
        text, method = extract_text(doc.file_path)
        doc.raw_text = text
        doc.extraction_method = method
        db.commit()

        # Stage 2: LLM extraction
        extracted = llm_extract(text)

        # Stage 3: validate
        validation = validate(extracted)

        # Stage 4: store, then either gate to pending_sync or fail.
        data["extracted_invoice"] = extracted
        data["validation_errors"] = validation["errors"]
        data["validation_warnings"] = validation["warnings"]
        data["extraction_method"] = method
        action.data = json.dumps(data)
        db.commit()

        if validation["errors"]:
            # Hard validation failure — do NOT push to Tally. The user gets a
            # WhatsApp message and the action shows up in the dashboard as failed.
            summary = "; ".join(validation["errors"][:3])
            _fail(db, action_id, summary)
            return

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
    d = json.loads(action.data)
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
