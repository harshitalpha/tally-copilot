# Tally Co-pilot — Complete System Spec (Simplified)
> Place this file at `tally-copilot/CLAUDE.md`. Give it to Claude Code.

---

## 1. What this system does

A user registers their WhatsApp number. From that point, any PDF or image they send to the platform's WhatsApp Business number is automatically extracted by AI and pushed to their connected Tally. No human approval step. No dashboard interaction required for the core flow.

**If phone is registered → process invoice → push to Tally → send confirmation**
**If phone is not registered → reply "Please register at app.yourproduct.com"**

---

## 2. Vocabulary

### Action types (v1)
- `UPLOAD_INVOICE_TO_TALLY` — user sends an invoice (WhatsApp or dashboard upload) to be extracted and pushed to Tally

### Action status flow
```
pending → processing → pending_sync → synced
                     → failed
```

| Status | Meaning |
|---|---|
| `pending` | File saved, queued for AI pipeline |
| `processing` | AI extraction running |
| `pending_sync` | Extraction done, waiting for Tally connector to pick up |
| `synced` | Connector pushed to Tally successfully |
| `failed` | Any error — pipeline or Tally sync |

---

## 3. Project Structure

```
tally-copilot/
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── auth.py
│   ├── requirements.txt
│   ├── .env
│   ├── uploads/                     ← created at runtime
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── onboarding.py
│   │   ├── actions.py
│   │   ├── documents.py
│   │   ├── whatsapp.py
│   │   ├── tally_connector.py
│   │   └── mock.py                  ← dev only
│   └── services/
│       ├── __init__.py
│       ├── pipeline.py
│       ├── extractor.py
│       ├── validator.py
│       └── whatsapp_sender.py
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── index.css
│       ├── App.jsx
│       ├── api.js
│       ├── pages/
│       │   ├── Login.jsx
│       │   ├── Signup.jsx
│       │   ├── Onboarding.jsx
│       │   ├── Dashboard.jsx        ← read-only history view
│       │   └── ActionDetail.jsx     ← read-only detail view
│       └── components/
│           ├── ProtectedRoute.jsx
│           ├── StatusBadge.jsx
│           └── MockPanel.jsx        ← dev only
└── tally-connector/
    ├── connector.py
    ├── tally_xml.py
    ├── requirements.txt
    └── .env
```

---

## 4. Database Schema

### File: `backend/database.py`

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./tally_copilot.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### File: `backend/models.py`

```python
from sqlalchemy import Column, String, Boolean, Text, DateTime, Integer, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from database import Base

def new_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id            = Column(String, primary_key=True, default=new_uuid)
    first_name    = Column(String, nullable=False)
    last_name     = Column(String, nullable=True)
    email         = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    is_onboarded  = Column(Boolean, default=False)
    # True after both WhatsApp and Tally are connected and configured
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    whatsapp_meta = relationship("UserWhatsappMetadata", back_populates="user", uselist=False)
    tally_meta    = relationship("UserTallyMetadata",    back_populates="user", uselist=False)
    actions       = relationship("UserAction",  back_populates="user")
    documents     = relationship("Document",    back_populates="user")


class UserWhatsappMetadata(Base):
    __tablename__ = "user_whatsapp_metadata"

    id             = Column(String, primary_key=True, default=new_uuid)
    user_id        = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    phone_number   = Column(String, nullable=False)
    # Registered phone in E.164 format: +91XXXXXXXXXX
    # When an invoice arrives from this number, it gets processed automatically
    is_verified    = Column(Boolean, default=False)
    otp_code       = Column(String, nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)
    verified_at    = Column(DateTime, nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="whatsapp_meta")


class UserTallyMetadata(Base):
    __tablename__ = "user_tally_metadata"

    id                      = Column(String, primary_key=True, default=new_uuid)
    user_id                 = Column(String, ForeignKey("users.id"), unique=True, nullable=False)

    # Pairing
    pairing_code            = Column(String, nullable=True)
    pairing_code_expires_at = Column(DateTime, nullable=True)
    is_paired               = Column(Boolean, default=False)
    paired_at               = Column(DateTime, nullable=True)
    connector_token         = Column(String, nullable=True, unique=True)
    # Issued to connector after pairing. Used in X-Connector-Token header.

    # Tally config (set during onboarding)
    company_name            = Column(String, nullable=True)
    company_gstin           = Column(String, nullable=True)
    purchase_ledger         = Column(String, nullable=True, default="Purchases")
    cgst_ledger_format      = Column(String, nullable=True, default="CGST @ {rate}%")
    sgst_ledger_format      = Column(String, nullable=True, default="SGST @ {rate}%")
    igst_ledger_format      = Column(String, nullable=True, default="IGST @ {rate}%")
    auto_create_ledgers     = Column(Boolean, default=True)
    available_ledgers       = Column(Text, nullable=True)
    # JSON array of {name, group} pushed by connector. Used for onboarding dropdowns.

    last_heartbeat_at       = Column(DateTime, nullable=True)
    # Connector sends every 60s. "Online" = last_heartbeat < 90s ago.

    created_at              = Column(DateTime, default=datetime.utcnow)
    updated_at              = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="tally_meta")


class Document(Base):
    __tablename__ = "documents"

    id                = Column(String, primary_key=True, default=new_uuid)
    user_id           = Column(String, ForeignKey("users.id"), nullable=False)
    original_filename = Column(String, nullable=True)
    stored_filename   = Column(String, nullable=False)
    file_path         = Column(String, nullable=False)
    file_type         = Column(String, nullable=False)   # pdf | jpg | jpeg | png | heic
    file_size_bytes   = Column(Integer, nullable=True)
    raw_text          = Column(Text, nullable=True)
    extraction_method = Column(String, nullable=True)    # pdfplumber | document_ai
    created_at        = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="documents")


class UserAction(Base):
    __tablename__ = "user_actions_data"

    id          = Column(String, primary_key=True, default=new_uuid)
    user_id     = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    action_type = Column(String, nullable=False)
    # UPLOAD_INVOICE_TO_TALLY
    status      = Column(String, nullable=False, default="pending", index=True)
    # pending | processing | pending_sync | synced | failed
    data        = Column(Text, nullable=False, default="{}")
    # JSON string. See Section 5 for shape.
    created_at  = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="actions")
```

---

## 5. Action Data Payload

### `UPLOAD_INVOICE_TO_TALLY` — `data` field

```json
{
  "document_id": "uuid",
  "source": "whatsapp | dashboard",
  "sender_phone": "+91XXXXXXXXXX | null",

  "extraction_method": "pdfplumber | document_ai | null",

  "extracted_invoice": {
    "supplier_name": "string | null",
    "supplier_gstin": "string | null",
    "invoice_number": "string | null",
    "invoice_date": "YYYY-MM-DD | null",
    "place_of_supply": "string | null",
    "reverse_charge": false,
    "line_items": [
      {
        "description": "string",
        "hsn_sac": "string | null",
        "quantity": 0.0,
        "unit": "string | null",
        "rate": 0.0,
        "taxable_amount": 0.0,
        "cgst_rate": 0.0,
        "cgst_amount": 0.0,
        "sgst_rate": 0.0,
        "sgst_amount": 0.0,
        "igst_rate": null,
        "igst_amount": null
      }
    ],
    "total_taxable_amount": 0.0,
    "total_cgst": 0.0,
    "total_sgst": 0.0,
    "total_igst": null,
    "total_amount": 0.0
  },

  "validation_errors": [],
  "validation_warnings": [],

  "tally_voucher_id": "string | null",
  "tally_error": "string | null"
}
```

---

## 6. Authentication

**Users:** `Authorization: Bearer <jwt_token>` on all protected endpoints.
**Connector:** `X-Connector-Token: <connector_token>` header.

### File: `backend/auth.py`

```python
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
import models, os
from typing import Optional

SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret-change-in-prod")
ALGORITHM  = "HS256"
EXPIRE_HRS = 24

pwd_context  = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()

def hash_password(p: str) -> str:           return pwd_context.hash(p)
def verify_password(p: str, h: str) -> bool: return pwd_context.verify(p, h)

def create_token(user_id: str) -> str:
    exp = datetime.utcnow() + timedelta(hours=EXPIRE_HRS)
    return jwt.encode({"sub": user_id, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def get_connector_user(
    x_connector_token: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> models.User:
    if not x_connector_token:
        raise HTTPException(status_code=401, detail="Missing connector token")
    meta = db.query(models.UserTallyMetadata).filter(
        models.UserTallyMetadata.connector_token == x_connector_token
    ).first()
    if not meta:
        raise HTTPException(status_code=401, detail="Invalid connector token")
    return db.query(models.User).filter(models.User.id == meta.user_id).first()
```

---

## 7. API Reference

Base URL: `http://localhost:8000/api`

---

### 7.1 Auth — `routes/auth.py`

#### POST /api/auth/signup
Auth: none
```json
// Request
{ "first_name": "Priya", "last_name": "Shah", "email": "priya@example.com", "password": "secret123" }

// 201 Response
{ "token": "jwt...", "user": { "id": "uuid", "first_name": "Priya", "email": "...", "is_onboarded": false } }

// 400 Error
{ "detail": "Email already registered" }
```

#### POST /api/auth/login
Auth: none
```json
// Request
{ "email": "priya@example.com", "password": "secret123" }

// 200 Response
{ "token": "jwt...", "user": { "id": "uuid", "first_name": "Priya", "email": "...", "is_onboarded": true } }

// 401 Error
{ "detail": "Invalid credentials" }
```

#### GET /api/auth/me
Auth: JWT
```json
// 200 Response
{
  "id": "uuid",
  "first_name": "Priya",
  "email": "priya@example.com",
  "is_onboarded": true,
  "whatsapp": { "phone_number": "+91XXXXXXXXXX", "is_verified": true },
  "tally": { "is_paired": true, "company_name": "Ramesh Traders Pvt Ltd", "connector_online": true }
}
```

---

### 7.2 Onboarding — `routes/onboarding.py`

#### POST /api/onboarding/whatsapp/connect
Auth: JWT
```json
// Request
{ "phone_number": "+91XXXXXXXXXX" }

// 200 Response
{
  "message": "OTP sent",
  "dev_otp": "123456"   // only when APP_ENV=development — show this on screen
}
```

#### POST /api/onboarding/whatsapp/verify
Auth: JWT
```json
// Request
{ "otp": "123456" }

// 200 Response
{ "verified": true, "phone_number": "+91XXXXXXXXXX" }

// 400 Error
{ "detail": "Invalid or expired OTP" }
```

#### POST /api/onboarding/tally/generate-pairing-code
Auth: JWT
Generates an 8-char code valid for 10 minutes.
```json
// 200 Response
{ "pairing_code": "K9X2MQRB", "expires_in_seconds": 600 }
```

#### GET /api/onboarding/tally/pairing-status
Auth: JWT
Frontend polls this every 3s while showing the pairing code.
```json
// Before pairing
{ "is_paired": false, "pairing_code": "K9X2MQRB", "expires_in_seconds": 420 }

// After connector pairs
{ "is_paired": true, "company_names": ["Ramesh Traders Pvt Ltd", "Ramesh Distributors"] }
```

#### POST /api/onboarding/tally/select-company
Auth: JWT
```json
// Request
{ "company_name": "Ramesh Traders Pvt Ltd" }
// 200 Response
{ "message": "Company selected" }
```

#### GET /api/onboarding/tally/ledgers
Auth: JWT
Returns ledger list pushed by connector. Used for mapping dropdowns.
```json
// 200 Response
{
  "ledgers": [
    { "name": "Purchases", "group": "Purchase Accounts" },
    { "name": "CGST @ 9%", "group": "Duties & Taxes" },
    { "name": "SGST @ 9%", "group": "Duties & Taxes" }
  ]
}
```

#### POST /api/onboarding/tally/save-mappings
Auth: JWT
Final onboarding step. Sets `is_onboarded = true`.
```json
// Request
{
  "purchase_ledger": "Purchases",
  "cgst_ledger_format": "CGST @ {rate}%",
  "sgst_ledger_format": "SGST @ {rate}%",
  "igst_ledger_format": "IGST @ {rate}%",
  "auto_create_ledgers": true
}
// 200 Response
{ "message": "Setup complete", "is_onboarded": true }
```

---

### 7.3 Actions — `routes/actions.py`

Read-only. No approve/reject/edit endpoints. The system handles everything automatically.

#### GET /api/actions
Auth: JWT
```
Query params: status (optional, comma-separated), limit (default 50), offset (default 0)
```
```json
// 200 Response
{
  "total": 12,
  "items": [
    {
      "id": "uuid",
      "action_type": "UPLOAD_INVOICE_TO_TALLY",
      "status": "synced",
      "data": { ... },
      "created_at": "2024-04-15T10:30:00",
      "updated_at": "2024-04-15T10:30:45"
    }
  ]
}
```

#### GET /api/actions/{action_id}
Auth: JWT
```json
// 200 Response
{
  "id": "uuid",
  "action_type": "UPLOAD_INVOICE_TO_TALLY",
  "status": "synced",
  "data": {
    "document_id": "uuid",
    "source": "whatsapp",
    "sender_phone": "+91XXXXXXXXXX",
    "extracted_invoice": { ... },
    "validation_errors": [],
    "validation_warnings": [],
    "tally_voucher_id": "12345",
    "tally_error": null
  },
  "created_at": "...",
  "updated_at": "..."
}
```

---

### 7.4 Documents — `routes/documents.py`

#### POST /api/documents/upload
Auth: JWT
Dashboard upload. Triggers same pipeline as WhatsApp flow.
```
Form data: file (PDF/JPG/PNG), source="dashboard"
```
```json
// 201 Response
{ "document_id": "uuid", "action_id": "uuid", "status": "pending" }
```

#### GET /api/documents/{document_id}/file
Auth: JWT
Serves the raw file for display. PDF → application/pdf, images → image/jpeg etc.

---

### 7.5 WhatsApp Webhook — `routes/whatsapp.py`

#### GET /api/whatsapp/webhook
Auth: none
Meta verification challenge. Returns `hub.challenge` as plain text if `hub.verify_token` matches `WHATSAPP_VERIFY_TOKEN` in .env.

#### POST /api/whatsapp/webhook
Auth: none

**This is the core of the system.** Meta calls this for every incoming message.
Must respond 200 within 5 seconds — all processing is in BackgroundTasks.

**Logic (simple):**

```python
@router.post("/webhook")
async def webhook(payload: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    message = _extract_message(payload)
    if not message:
        return {"status": "ok"}

    sender_phone = message["from"]

    # Check registration
    wa_meta = db.query(UserWhatsappMetadata).filter(
        UserWhatsappMetadata.phone_number == sender_phone,
        UserWhatsappMetadata.is_verified == True
    ).first()

    if not wa_meta:
        # Not registered — send error reply and stop
        background_tasks.add_task(
            whatsapp_sender.send_text,
            sender_phone,
            "You are not registered. Please sign up at app.yourproduct.com"
        )
        return {"status": "ok"}

    # Registered — only process document/image messages
    if message["type"] not in ("document", "image"):
        return {"status": "ok"}

    background_tasks.add_task(
        handle_incoming_invoice,
        user_id=wa_meta.user_id,
        message=message,
        sender_phone=sender_phone
    )
    return {"status": "ok"}
```

**`handle_incoming_invoice(user_id, message, sender_phone)` function:**
1. Download media file from Meta's API using `message["media_id"]`
2. Save file to `uploads/` directory, create `Document` record
3. Create `UserAction` with `status=pending`, `data.source="whatsapp"`, `data.sender_phone=sender_phone`
4. Call `run_pipeline(action_id)`

```json
// Meta webhook payload shape (simplified):
{
  "entry": [{
    "changes": [{
      "value": {
        "messages": [{
          "from": "+91XXXXXXXXXX",
          "type": "document | image | text",
          "document": { "id": "media_id", "mime_type": "application/pdf", "filename": "invoice.pdf" },
          "image":    { "id": "media_id", "mime_type": "image/jpeg" }
        }]
      }
    }]
  }]
}

// Always respond immediately:
{ "status": "ok" }
```

---

### 7.6 Tally Connector Routes — `routes/tally_connector.py`

All use `X-Connector-Token` header (except `/pair`).

#### POST /api/tally/pair
Auth: none
```json
// Request
{
  "pairing_code": "K9X2MQRB",
  "company_names": ["Ramesh Traders Pvt Ltd", "Ramesh Distributors"]
}
// 200 Response
{ "connector_token": "long_random_64_char_token", "message": "Paired" }
// 400 Error
{ "detail": "Invalid or expired pairing code" }
```

#### POST /api/tally/heartbeat
Auth: Connector-Token
```json
// Request: {} or empty
// 200 Response
{ "ok": true, "config_updated": false }
// config_updated=true means connector should re-fetch config
```

#### GET /api/tally/config
Auth: Connector-Token
```json
// 200 Response
{
  "company_name": "Ramesh Traders Pvt Ltd",
  "purchase_ledger": "Purchases",
  "cgst_ledger_format": "CGST @ {rate}%",
  "sgst_ledger_format": "SGST @ {rate}%",
  "igst_ledger_format": "IGST @ {rate}%",
  "auto_create_ledgers": true
}
```

#### POST /api/tally/ledgers
Auth: Connector-Token
```json
// Request
{ "ledgers": [{ "name": "Purchases", "group": "Purchase Accounts" }, ...] }
// 200 Response
{ "stored": 47 }
```

#### GET /api/tally/actions/pending-sync
Auth: Connector-Token
Returns actions in `pending_sync` status for this user's account.
```json
// 200 Response
[
  {
    "id": "action_uuid",
    "data": {
      "document_id": "uuid",
      "source": "whatsapp",
      "extracted_invoice": { ... }
    }
  }
]
// Empty array if nothing pending
```

#### POST /api/tally/actions/{action_id}/sync-complete
Auth: Connector-Token
Updates status to `synced`. Sends WhatsApp confirmation to the user.
```json
// Request
{ "voucher_id": "12345" }
// 200 Response
{ "status": "synced" }
```

#### POST /api/tally/actions/{action_id}/sync-failed
Auth: Connector-Token
Updates status to `failed`. Sends WhatsApp error message to the user.
```json
// Request
{ "error": "Ledger not found: Suresh Enterprises" }
// 200 Response
{ "status": "failed" }
```

**Implementation of both sync routes — send WhatsApp message after updating status:**

```python
@router.post("/{action_id}/sync-complete")
def sync_complete(action_id: str, data: dict, db: Session = Depends(get_db),
                  connector_user: models.User = Depends(get_connector_user)):
    action = db.query(models.UserAction).filter(models.UserAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404)

    d = json.loads(action.data)
    d["tally_voucher_id"] = data.get("voucher_id", "")
    action.data = json.dumps(d)
    action.status = "synced"
    db.commit()

    # Send WhatsApp confirmation to the sender
    wa = db.query(models.UserWhatsappMetadata).filter(
        models.UserWhatsappMetadata.user_id == action.user_id,
        models.UserWhatsappMetadata.is_verified == True
    ).first()
    if wa:
        inv = d.get("extracted_invoice", {})
        sender_phone = d.get("sender_phone") or wa.phone_number
        whatsapp_sender.send_confirmation(
            phone=sender_phone,
            supplier=inv.get("supplier_name", "Unknown"),
            amount=inv.get("total_amount", 0),
            voucher_id=data.get("voucher_id", "")
        )
    return {"status": "synced"}


@router.post("/{action_id}/sync-failed")
def sync_failed(action_id: str, data: dict, db: Session = Depends(get_db),
                connector_user: models.User = Depends(get_connector_user)):
    action = db.query(models.UserAction).filter(models.UserAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404)

    d = json.loads(action.data)
    d["tally_error"] = data.get("error", "Unknown error")
    action.data = json.dumps(d)
    action.status = "failed"
    db.commit()

    wa = db.query(models.UserWhatsappMetadata).filter(
        models.UserWhatsappMetadata.user_id == action.user_id,
        models.UserWhatsappMetadata.is_verified == True
    ).first()
    if wa:
        d2 = json.loads(action.data)
        sender_phone = d2.get("sender_phone") or wa.phone_number
        whatsapp_sender.send_failure(
            phone=sender_phone,
            error=data.get("error", "Unknown error")
        )
    return {"status": "failed"}
```

---

### 7.7 Mock Routes — `routes/mock.py` (dev only)

Only loaded when `APP_ENV=development`.

#### POST /api/mock/whatsapp/incoming
Simulates a user sending an invoice via WhatsApp.
The `sender_phone` must match a registered phone in `user_whatsapp_metadata`.
```
Form data:
  file: File (PDF or image)
  sender_phone: string  ← must be a registered, verified phone
```
```json
// If phone is not registered → 200 with error message:
{ "result": "not_registered", "message": "Phone +91X not found in user_whatsapp_metadata" }

// If registered → triggers full pipeline:
{ "result": "processing", "action_id": "uuid" }
```

#### POST /api/mock/tally/voucher
Simulates Tally accepting a voucher.
Set `TALLY_URL=http://localhost:8000/api/mock/tally/voucher` in connector's .env.
```
Request: raw XML (ignored)
Response 200: raw XML
```
```xml
<RESPONSE><CREATED>1</CREATED><ALTERED>0</ALTERED><ERRORS>0</ERRORS><LASTVCHID>99999</LASTVCHID></RESPONSE>
```

#### GET /api/mock/whatsapp/send-log
Returns all outbound WhatsApp messages (stored in memory during dev).
```json
// 200 Response
[
  {
    "to": "+91XXXXXXXXXX",
    "type": "confirmation | failure | unregistered",
    "message_text": "✅ Posted to Tally...",
    "sent_at": "ISO datetime"
  }
]
```

---

## 8. Services

### File: `backend/services/whatsapp_sender.py`

```python
import os
from datetime import datetime

_send_log = []  # In-memory log for dev mode

def send_text(phone: str, text: str, msg_type: str = "generic"):
    """Send any plain text message to a phone number."""
    _log(phone, text, msg_type)
    if os.getenv("APP_ENV") != "development":
        # TODO: POST to Meta Graph API
        pass

def send_confirmation(phone: str, supplier: str, amount: float, voucher_id: str):
    msg = (
        f"✅ Posted to Tally\n"
        f"{supplier} · ₹{amount:,.2f}\n"
        f"Tally Voucher #{voucher_id}"
    )
    send_text(phone, msg, "confirmation")

def send_failure(phone: str, error: str):
    msg = (
        f"❌ Could not process invoice\n"
        f"Reason: {error}\n"
        f"Please try again with a clearer photo, or upload via dashboard."
    )
    send_text(phone, msg, "failure")

def _log(phone: str, text: str, msg_type: str):
    entry = {"to": phone, "type": msg_type, "message_text": text, "sent_at": datetime.utcnow().isoformat()}
    _send_log.append(entry)
    print(f"\n[WA → {phone}]\n{text}\n")

def get_send_log():
    return _send_log
```

### File: `backend/services/extractor.py`

```python
import pdfplumber, anthropic, json, os
from dotenv import load_dotenv

load_dotenv()
_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are an Indian GST invoice data extraction system.
Extract invoice data and return ONLY valid JSON. No markdown, no explanation, no code blocks. Raw JSON only.

Return exactly this structure:
{
  "supplier_name": "string",
  "supplier_gstin": "15-char GSTIN or null",
  "invoice_number": "string",
  "invoice_date": "YYYY-MM-DD",
  "place_of_supply": "string or null",
  "reverse_charge": false,
  "line_items": [
    {
      "description": "string",
      "hsn_sac": "string or null",
      "quantity": 1.0,
      "unit": "string or null",
      "rate": 0.0,
      "taxable_amount": 0.0,
      "cgst_rate": 9.0,
      "cgst_amount": 0.0,
      "sgst_rate": 9.0,
      "sgst_amount": 0.0,
      "igst_rate": null,
      "igst_amount": null
    }
  ],
  "total_taxable_amount": 0.0,
  "total_cgst": 0.0,
  "total_sgst": 0.0,
  "total_igst": null,
  "total_amount": 0.0
}
Rules:
1. Amounts are plain numbers. Strip ₹ and commas. "1,23,456.00" → 123456.0
2. Dates to YYYY-MM-DD. "10/04/24" → "2024-04-10"
3. GSTIN: exactly 15 chars. Return null if not found.
4. If IGST present, cgst_*/sgst_* fields are null (and vice versa).
5. reverse_charge true only if invoice explicitly says "Reverse Charge: Yes".
6. Missing fields return null. Never guess."""


def extract_text(pdf_path: str) -> tuple[str, str]:
    text = _extract_with_pdfplumber(pdf_path)
    if len(text.strip()) > 50 and any(c.isdigit() for c in text):
        return text, "pdfplumber"
    return text, "pdfplumber_low_confidence"

def _extract_with_pdfplumber(path: str) -> str:
    full = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            full += (page.extract_text() or "") + "\n"
            for table in page.extract_tables():
                for row in table:
                    if row:
                        full += " | ".join(str(c or "").strip() for c in row) + "\n"
    return full.strip()

def llm_extract(text: str) -> dict:
    truncated = text[:4000]
    response = _client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Extract invoice data:\n\n{truncated}"}]
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1][4:] if len(parts) > 1 else raw
    return json.loads(raw.strip("` \n"))
```

### File: `backend/services/validator.py`

```python
import re
from datetime import date as date_type

def validate(data: dict) -> dict:
    errors, warnings = [], []
    if data.get("supplier_gstin"):
        if not re.match(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$",
                        str(data["supplier_gstin"]).upper()):
            errors.append(f"Invalid GSTIN: {data['supplier_gstin']}")
    for item in data.get("line_items", []):
        for tax in ["cgst", "sgst", "igst"]:
            r, a, t = item.get(f"{tax}_rate"), item.get(f"{tax}_amount"), item.get("taxable_amount")
            if r and a and t:
                exp = round(float(t) * float(r) / 100, 2)
                if abs(exp - float(a)) > 2:
                    warnings.append(f"{tax.upper()} mismatch on '{item.get('description')}': expected {exp}, got {a}")
    calc = sum(float(data.get(k) or 0) for k in ["total_taxable_amount","total_cgst","total_sgst","total_igst"])
    stated = float(data.get("total_amount") or 0)
    if stated > 0 and abs(calc - stated) > 5:
        warnings.append(f"Total mismatch: calculated {calc:.2f}, stated {stated:.2f}")
    if data.get("invoice_date"):
        try:
            if date_type.fromisoformat(data["invoice_date"]) > date_type.today():
                errors.append("Invoice date is in the future")
        except ValueError:
            errors.append(f"Invalid date: {data['invoice_date']}")
    return {"errors": errors, "warnings": warnings}
```

### File: `backend/services/pipeline.py`

```python
import json
from datetime import datetime
from database import SessionLocal
from models import UserAction, Document
from services.extractor import extract_text, llm_extract
from services.validator import validate
from services import whatsapp_sender


def run_pipeline(action_id: str):
    """
    Full pipeline: extract → validate → mark pending_sync.
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
        doc  = db.query(Document).filter(Document.id == data["document_id"]).first()

        # Stage 1: extract text
        text, method = extract_text(doc.file_path)
        doc.raw_text = text
        doc.extraction_method = method
        db.commit()

        # Stage 2: LLM extraction
        extracted = llm_extract(text)

        # Stage 3: validate
        validation = validate(extracted)

        # Stage 4: store and mark ready for connector
        data["extracted_invoice"] = extracted
        data["validation_errors"] = validation["errors"]
        data["validation_warnings"] = validation["warnings"]
        data["extraction_method"] = method
        action.data = json.dumps(data)
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

    # Send WhatsApp failure message to the sender
    from models import UserWhatsappMetadata
    wa = db.query(UserWhatsappMetadata).filter(
        UserWhatsappMetadata.user_id == action.user_id,
        UserWhatsappMetadata.is_verified == True
    ).first()
    if wa:
        sender_phone = d.get("sender_phone") or wa.phone_number
        whatsapp_sender.send_failure(sender_phone, error)
```

---

## 9. Backend Config

### `backend/.env`
```
APP_ENV=development
JWT_SECRET=dev-secret-change-in-prod
ANTHROPIC_API_KEY=your_key_here
WHATSAPP_VERIFY_TOKEN=any-string-for-local-dev
```

### `backend/requirements.txt`
```
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.30
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
pdfplumber==0.11.0
anthropic==0.25.0
python-multipart==0.0.9
python-dotenv==1.0.1
httpx==0.27.0
```

### `backend/main.py`
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
import models, os
from dotenv import load_dotenv

load_dotenv()
from routes import auth, onboarding, actions, documents, whatsapp, tally_connector

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Tally Co-pilot", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,            prefix="/api/auth")
app.include_router(onboarding.router,      prefix="/api/onboarding")
app.include_router(actions.router,         prefix="/api/actions")
app.include_router(documents.router,       prefix="/api/documents")
app.include_router(whatsapp.router,        prefix="/api/whatsapp")
app.include_router(tally_connector.router, prefix="/api/tally")

if os.getenv("APP_ENV") == "development":
    from routes import mock
    app.include_router(mock.router, prefix="/api/mock")

@app.get("/health")
def health():
    return {"status": "ok", "env": os.getenv("APP_ENV", "production")}
```

---

## 10. Tally Connector

### `tally-connector/.env` (local dev — no real Tally)
```
BACKEND_URL=http://localhost:8000
TALLY_URL=http://localhost:8000/api/mock/tally/voucher
POLL_INTERVAL_SECONDS=10
```

### `tally-connector/requirements.txt`
```
requests==2.31.0
python-dotenv==1.0.1
```

### `tally-connector/tally_xml.py`
```python
def build_purchase_voucher_xml(inv: dict, config: dict) -> str:
    date    = (inv.get("invoice_date") or "").replace("-", "")
    sup     = inv.get("supplier_name") or "Unknown Supplier"
    inv_no  = inv.get("invoice_number") or ""
    total   = float(inv.get("total_amount") or 0)
    taxable = float(inv.get("total_taxable_amount") or 0)
    cgst    = float(inv.get("total_cgst") or 0)
    sgst    = float(inv.get("total_sgst") or 0)
    igst    = float(inv.get("total_igst") or 0)
    items   = inv.get("line_items") or []
    cgst_r  = float((items[0].get("cgst_rate") or 0)) if items else 0
    igst_r  = float((items[0].get("igst_rate") or 0)) if items else 0

    entries = [
        {"name": config.get("purchase_ledger", "Purchases"), "amount": -taxable, "pos": "No"}
    ]
    if cgst > 0:
        r = int(cgst_r)
        entries.append({"name": config.get("cgst_ledger_format","CGST @ {rate}%").replace("{rate}",str(r)), "amount": -cgst, "pos":"No"})
        entries.append({"name": config.get("sgst_ledger_format","SGST @ {rate}%").replace("{rate}",str(r)), "amount": -sgst, "pos":"No"})
    if igst > 0:
        r = int(igst_r)
        entries.append({"name": config.get("igst_ledger_format","IGST @ {rate}%").replace("{rate}",str(r)), "amount": -igst, "pos":"No"})
    entries.append({"name": sup, "amount": total, "pos": "Yes"})

    ledger_xml = "".join(
        f"<ALLLEDGERENTRIES.LIST><LEDGERNAME>{e['name']}</LEDGERNAME>"
        f"<ISDEEMEDPOSITIVE>{e['pos']}</ISDEEMEDPOSITIVE><AMOUNT>{e['amount']:.2f}</AMOUNT>"
        f"</ALLLEDGERENTRIES.LIST>"
        for e in entries
    )
    return (
        f"<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>"
        f"<BODY><IMPORTDATA><REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME>"
        f"<STATICVARIABLES><SVCURRENTCOMPANY>{config.get('company_name','')}</SVCURRENTCOMPANY></STATICVARIABLES>"
        f"</REQUESTDESC><REQUESTDATA><TALLYMESSAGE xmlns:UDF=\"TallyUDF\">"
        f"<VOUCHER VCHTYPE=\"Purchase\" ACTION=\"Create\">"
        f"<DATE>{date}</DATE>"
        f"<NARRATION>Purchase from {sup} | Invoice: {inv_no}</NARRATION>"
        f"<VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>"
        f"<PARTYLEDGERNAME>{sup}</PARTYLEDGERNAME>"
        f"<ISINVOICE>Yes</ISINVOICE>{ledger_xml}"
        f"</VOUCHER></TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"
    )
```

### `tally-connector/connector.py`
```python
import os, time, json, re, requests
from dotenv import load_dotenv
from tally_xml import build_purchase_voucher_xml

load_dotenv()
BACKEND        = os.getenv("BACKEND_URL", "http://localhost:8000")
TALLY          = os.getenv("TALLY_URL",   "http://localhost:8000/api/mock/tally/voucher")
POLL           = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
STATE_FILE     = "connector_state.json"


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def headers(state: dict) -> dict:
    return {"X-Connector-Token": state["connector_token"]}


def pair(state: dict) -> dict:
    code = input("Enter the pairing code shown in your dashboard: ").strip().upper()
    resp = requests.post(f"{BACKEND}/api/tally/pair", json={
        "pairing_code": code,
        "company_names": ["Mock Company Pvt Ltd"]
    }, timeout=10)
    if resp.status_code == 200:
        state["connector_token"] = resp.json()["connector_token"]
        save_state(state)
        print("Paired successfully!")
        return state
    else:
        print(f"Pairing failed: {resp.json().get('detail')}")
        exit(1)


def fetch_config(state: dict) -> dict:
    r = requests.get(f"{BACKEND}/api/tally/config", headers=headers(state), timeout=5)
    if r.status_code == 200:
        state["config"] = r.json()
        save_state(state)
    return state.get("config", {})


def heartbeat(state: dict):
    try:
        r = requests.post(f"{BACKEND}/api/tally/heartbeat", headers=headers(state), json={}, timeout=5)
        if r.status_code == 200 and r.json().get("config_updated"):
            fetch_config(state)
    except Exception:
        pass


def extract_voucher_id(xml: str) -> str:
    m = re.search(r"<LASTVCHID>(\w+)</LASTVCHID>", xml)
    return m.group(1) if m else ""


def process_action(action: dict, config: dict, state: dict):
    action_id = action["id"]
    inv = action["data"].get("extracted_invoice", {})
    supplier = inv.get("supplier_name", "Unknown")
    amount   = inv.get("total_amount", 0)
    print(f"  Syncing: {supplier} | ₹{amount}")

    xml = build_purchase_voucher_xml(inv, config)
    try:
        r = requests.post(
            TALLY, data=xml.encode("utf-8"),
            headers={"Content-Type": "application/xml"}, timeout=15
        )
        if "ERRORS>0" in r.text or "<LINEERROR>" in r.text:
            err = r.text[:300]
            print(f"  ✗ Tally error: {err}")
            requests.post(f"{BACKEND}/api/tally/actions/{action_id}/sync-failed",
                          headers=headers(state), json={"error": err})
        else:
            vid = extract_voucher_id(r.text)
            print(f"  ✓ Synced. Voucher: {vid}")
            requests.post(f"{BACKEND}/api/tally/actions/{action_id}/sync-complete",
                          headers=headers(state), json={"voucher_id": vid})
    except requests.ConnectionError:
        err = f"Tally not reachable at {TALLY}"
        print(f"  ✗ {err}")
        requests.post(f"{BACKEND}/api/tally/actions/{action_id}/sync-failed",
                      headers=headers(state), json={"error": err})


def poll_loop(state: dict):
    config = fetch_config(state)
    print(f"Company : {config.get('company_name', 'not set')}")
    print(f"Polling every {POLL}s — Ctrl+C to stop\n")
    while True:
        try:
            heartbeat(state)
            config = state.get("config", {})
            r = requests.get(f"{BACKEND}/api/tally/actions/pending-sync",
                             headers=headers(state), timeout=5)
            actions = r.json()
            if actions:
                print(f"[{len(actions)} to sync]")
                for a in actions:
                    process_action(a, config, state)
            else:
                print(".", end="", flush=True)
        except requests.ConnectionError:
            print(f"\n[backend offline]", end="", flush=True)
        except Exception as e:
            print(f"\n[error: {e}]", end="", flush=True)
        time.sleep(POLL)


def main():
    print("=" * 45)
    print("Tally Co-pilot Connector")
    print(f"Backend : {BACKEND}")
    print(f"Tally   : {TALLY}")
    print("=" * 45)
    state = load_state()
    if not state.get("connector_token"):
        state = pair(state)
    poll_loop(state)

if __name__ == "__main__":
    main()
```

---

## 11. Frontend

### Setup
```bash
cd tally-copilot
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install -D tailwindcss postcss autoprefixer && npx tailwindcss init -p
npm install react-router-dom
```

### `tailwind.config.js`
```js
export default { content: ["./index.html", "./src/**/*.{js,jsx}"], theme: { extend: {} }, plugins: [] }
```

### `src/index.css`
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

### `src/App.jsx`
```jsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'
import ActionDetail from './pages/ActionDetail'
import ProtectedRoute from './components/ProtectedRoute'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login"       element={<Login />} />
        <Route path="/signup"      element={<Signup />} />
        <Route path="/onboarding"  element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />
        <Route path="/dashboard"   element={<ProtectedRoute requireOnboarded><Dashboard /></ProtectedRoute>} />
        <Route path="/actions/:id" element={<ProtectedRoute requireOnboarded><ActionDetail /></ProtectedRoute>} />
        <Route path="*"            element={<Navigate to="/dashboard" />} />
      </Routes>
    </BrowserRouter>
  )
}
```

### `ProtectedRoute` logic
- No JWT in localStorage → redirect to `/login`
- Has JWT but `user.is_onboarded=false` and `requireOnboarded=true` → redirect to `/onboarding`
- Has JWT and `user.is_onboarded=true` and on `/onboarding` → redirect to `/dashboard`

### Pages to build

**Login.jsx:** email + password → `POST /api/auth/login` → save token → go to `/dashboard`

**Signup.jsx:** first_name, email, password → `POST /api/auth/signup` → save token → go to `/onboarding`

**Onboarding.jsx:** Three-step wizard:
- Step 1 — WhatsApp: enter phone → send OTP → show `dev_otp` in green box → enter OTP → verify
- Step 2 — Tally pair: click "Generate Code" → show code large → poll `/api/onboarding/tally/pairing-status` every 3s → on paired, show company dropdown → select
- Step 3 — Ledger mappings: fetch ledgers from `/api/onboarding/tally/ledgers` → 4 text inputs (pre-filled with defaults) → save → redirect to `/dashboard`

**Dashboard.jsx:** Read-only history view
- Header: firm name + status badges (WA connected ✓, Tally online ✓) from `GET /api/auth/me`
- Upload zone at top: drag-drop or click → `POST /api/documents/upload` → entry appears
- List of actions, newest first, polls every 3 seconds
- Each row: supplier name / invoice number / amount / status badge / time
- Click row → go to `/actions/:id`
- Dev panel at bottom (only when `import.meta.env.DEV`): `MockPanel` component

**ActionDetail.jsx:** Read-only detail view
- Two-panel layout (50/50)
- Left: iframe or img pointing to `GET /api/documents/{doc_id}/file`
- Right:
  - Status badge (large)
  - If `failed`: red error box with `tally_error`
  - If `synced`: green box with `tally_voucher_id`
  - Extracted invoice fields displayed (not editable — read only)
  - Validation errors/warnings if any

**MockPanel.jsx (dev only):**
- File picker + phone number input (pre-filled with a registered phone)
- "Simulate WhatsApp Invoice" button → `POST /api/mock/whatsapp/incoming`
- Below: "WA Send Log" — fetches `GET /api/mock/whatsapp/send-log` every 3s — shows messages sent

### `src/api.js`
```js
const BASE  = 'http://localhost:8000/api'
const tok   = () => localStorage.getItem('token')
const jh    = () => ({ 'Authorization': `Bearer ${tok()}`, 'Content-Type': 'application/json' })
const fh    = () => ({ 'Authorization': `Bearer ${tok()}` })

export const signup          = d  => fetch(`${BASE}/auth/signup`,  { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(d) }).then(r=>r.json())
export const login           = d  => fetch(`${BASE}/auth/login`,   { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(d) }).then(r=>r.json())
export const getMe           = () => fetch(`${BASE}/auth/me`,      { headers:jh() }).then(r=>r.json())

export const connectWA       = p  => fetch(`${BASE}/onboarding/whatsapp/connect`,           { method:'POST', headers:jh(), body:JSON.stringify({phone_number:p}) }).then(r=>r.json())
export const verifyWA        = o  => fetch(`${BASE}/onboarding/whatsapp/verify`,             { method:'POST', headers:jh(), body:JSON.stringify({otp:o}) }).then(r=>r.json())
export const genPairingCode  = () => fetch(`${BASE}/onboarding/tally/generate-pairing-code`, { method:'POST', headers:jh() }).then(r=>r.json())
export const getPairingStatus= () => fetch(`${BASE}/onboarding/tally/pairing-status`,        { headers:jh() }).then(r=>r.json())
export const selectCompany   = n  => fetch(`${BASE}/onboarding/tally/select-company`,        { method:'POST', headers:jh(), body:JSON.stringify({company_name:n}) }).then(r=>r.json())
export const getLedgers      = () => fetch(`${BASE}/onboarding/tally/ledgers`,               { headers:jh() }).then(r=>r.json())
export const saveMappings    = d  => fetch(`${BASE}/onboarding/tally/save-mappings`,         { method:'POST', headers:jh(), body:JSON.stringify(d) }).then(r=>r.json())

export const getActions      = (q='') => fetch(`${BASE}/actions?${q}`,      { headers:jh() }).then(r=>r.json())
export const getAction       = id     => fetch(`${BASE}/actions/${id}`,      { headers:jh() }).then(r=>r.json())

export const uploadDocument  = file  => { const f=new FormData(); f.append('file',file); f.append('source','dashboard'); return fetch(`${BASE}/documents/upload`,{method:'POST',headers:fh(),body:f}).then(r=>r.json()) }

export const mockIncoming    = (file,phone) => { const f=new FormData(); f.append('file',file); f.append('sender_phone',phone); return fetch(`${BASE}/mock/whatsapp/incoming`,{method:'POST',body:f}).then(r=>r.json()) }
export const getMockWALog    = () => fetch(`${BASE}/mock/whatsapp/send-log`).then(r=>r.json())
```

---

## 12. Build Order

```
Step 1:  backend/ — database.py, models.py, auth.py, main.py
         Run: uvicorn main:app --reload --port 8000
         Test: GET /health → {"status":"ok","env":"development"}

Step 2:  routes/auth.py
         Test: POST /api/auth/signup → get token, POST /api/auth/login

Step 3:  services/extractor.py, services/validator.py
         Test: call llm_extract() directly on sample invoice text

Step 4:  routes/mock.py
         Test: POST /api/mock/tally/voucher → XML response

Step 5:  routes/tally_connector.py, routes/onboarding.py
         Test: full pairing flow via curl

Step 6:  routes/documents.py, services/pipeline.py
         Test: upload PDF → action goes pending→processing→pending_sync

Step 7:  services/whatsapp_sender.py, routes/whatsapp.py
         Test: POST /api/mock/whatsapp/incoming with registered phone + PDF

Step 8:  routes/actions.py
         Test: GET /api/actions → see the processed entry

Step 9:  tally-connector/ — connector.py, tally_xml.py
         Test: run connector, pair it, watch it sync pending_sync entries

Step 10: frontend/ — Login → Signup → Onboarding → Dashboard → ActionDetail
```

---

## 13. End-to-End Test (no real WhatsApp, no real Tally)

**3 terminals:**
```bash
# T1: cd backend  && uvicorn main:app --reload --port 8000
# T2: cd frontend && npm run dev     (http://localhost:5173)
# T3: cd tally-connector && python connector.py
```

1. Open http://localhost:5173 → Signup
2. Onboarding Step 1: enter `+91MOCK12345` → Send OTP → screen shows dev OTP → enter it → verified
3. Onboarding Step 2: Generate Code (e.g. `K9X2MQRB`) → T3 connector prompts for code → type it → "Paired!" → select "Mock Company Pvt Ltd"
4. Onboarding Step 3: accept default ledger mappings → Finish → redirected to dashboard
5. On dashboard, open dev panel → enter phone `+91MOCK12345` (same registered phone) → upload any invoice PDF → click "Simulate WhatsApp Invoice"
6. Action appears: `pending` → `processing` → `pending_sync`
7. T3 shows: `[1 to sync]` → `✓ Synced. Voucher: 99999`
8. Action changes to `synced`
9. WA Send Log shows: `✅ Posted to Tally — [supplier] · ₹[amount] · Voucher #99999`

**Test unregistered phone:**
```bash
curl -X POST http://localhost:8000/api/mock/whatsapp/incoming \
  -F "file=@invoice.pdf" \
  -F "sender_phone=+91UNKNOWN99"
# Response: {"result":"not_registered","message":"Phone +91UNKNOWN99 not found..."}
```

**WA Send Log shows the error reply that would go to the unregistered number.**
