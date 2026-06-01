# Tally Co-pilot — Working Notes

> Full system spec: see [`complete_architecture.md`](./complete_architecture.md).
> This file is the short, important stuff to keep in working memory.

---

## What this is

Users sign up with email, verify their email via OTP, then connect Tally. From the
dashboard they can upload invoice PDFs or images. When WhatsApp is wired up (later),
invoices sent from a registered number are auto-processed.

**Flow:** file uploaded → AI-extracted (Gemini/Claude) → GST-validated → pushed to
Tally as a Purchase voucher → confirmed via WhatsApp (or dashboard).

---

## Project layout

```
tally-copilot/
├── backend/           FastAPI + SQLite, AI pipeline, all routes
│   ├── ports/           LLMClient, ObjectStore, Messenger, EmailClient protocols
│   ├── adapters/        Vendor implementations (gemini, anthropic, resend, s3, …)
│   ├── infra/           Registry, router, telemetry, crypto, catalog, seed
│   ├── routes/          auth, onboarding, actions, documents, whatsapp,
│   │                    tally_connector, infra, settings, mock
│   └── services/        extractor, validator, pipeline, whatsapp_sender, email_sender
├── frontend/          React + Vite + Tailwind v3
│   └── pages/           Landing, Login, Signup, ForgotPassword, ResetPassword,
│                        Onboarding, Dashboard, ActionDetail, Settings, Infrastructure
└── tally-connector/   Polling daemon (installable via pip as tally-copilot-connector)
```

The DB (`backend/tally_copilot.db`) is disposable in dev — delete to reset schema.

---

## Action status flow

```
pending → processing → pending_review (if require_review=True) → pending_sync → synced
                     → failed
```

- `pending_review` — user must approve in dashboard before connector picks it up
- `pending_sync` — connector polls for these and pushes to Tally
- `synced` / `failed` — terminal; WhatsApp confirmation/failure sent

---

## Auth model

- **Email OTP** at signup — user must verify before onboarding proceeds.
  `dev_otp` is returned in the signup response when `APP_ENV=development`.
- **Password reset** via email link (1h expiry). Uses `email_sender.send_password_reset`.
- **Onboarding completes** when: `email_verified=True` AND Tally paired + company
  selected + mappings saved. WhatsApp is now **optional** (add from Settings later).
- **User JWT**: `Authorization: Bearer <token>` (HS256, 24h).
- **Connector**: `X-Connector-Token` — re-issued on each generate-pairing-code call.

---

## Infrastructure control plane (`/settings/infra`)

Providers + routing rules live in the DB (encrypted with Fernet). Surfaces:
- `llm` — Gemini/Claude/OpenAI-compat. Tasks: `extract_invoice`, `extract_invoice_image`
- `object_store` — local_fs / S3-compat
- `messenger` — inmemory / Meta Cloud API
- `email` — inmemory / Resend

On first boot, `infra/seed.py` reads `.env` and creates default rows. After that
the dashboard owns all config. Registry hot-reloads on `routing_rules.version` bump.

---

## Extraction — PDF vs image

`services/extractor.py:extract_and_classify(file_path, file_type)` branches:
- **PDF** → pdfplumber text → text LLM via router (`task=extract_invoice`)
- **image (JPG/PNG/HEIC)** → bytes → Gemini Vision (`task=extract_invoice_image`,
  adapter must have `extract_json_from_image` — GeminiAdapter does)

Vision model defaults to `gemini-2.0-flash`. Override in `/settings/infra` → Providers
→ gemini-default → `vision_model` field.

---

## How to run (3 terminals)

```bash
# T1 — backend (delete tally_copilot.db first if schema changed)
cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8000

# T2 — frontend
cd frontend && env HOME=/tmp/x npm run dev   # http://localhost:5173

# T3 — connector
cd tally-connector && python connector.py
```

**Required env** (`backend/.env`):
```
APP_ENV=development
JWT_SECRET=anything-for-dev
WHATSAPP_VERIFY_TOKEN=anything-for-dev
GEMINI_API_KEY=AIza...              # primary LLM + vision
RESEND_API_KEY=re_...               # optional; falls back to in-memory log
RESEND_FROM_EMAIL=noreply@resend.dev
# ANTHROPIC_API_KEY=sk-ant-...     # optional fallback LLM
# INFRA_MASTER_KEY=...             # optional; dev uses deterministic fallback key
# APP_URL=http://localhost:5173    # used in password reset emails
```

---

## Environment quirks (Python 3.14 macOS)

- **`sqlalchemy>=2.0.36`** — older versions crash on import.
- **`bcrypt==4.0.1`** — bcrypt 4.1+ breaks passlib.
- **Node**: `brew install node` → `/opt/homebrew/bin/node`.
- **npm**: `env HOME=/tmp/x npm ...` + project `.npmrc` with `registry=https://registry.npmjs.org/`.

---

## Known fixes (don't re-introduce)

- **Connector error check**: `_has_error()` uses regex `<ERRORS>(\d+)</ERRORS>` — the
  naive `"ERRORS>0" in text` substring match false-positives on success responses.
- **ProtectedRoute**: uses `useLocation` + re-fetches `/me` on path change.
- **Onboarding**: `_maybe_mark_onboarded` no longer requires WhatsApp — only email
  verified + Tally paired + company + mappings.

---

## Deployment

- **Backend**: `backend/Dockerfile` + `railway.toml` → Railway.app
- **Frontend**: `frontend/vercel.json` → Vercel (static, SPA rewrites configured)
- **Connector**: `pip install tally-copilot-connector` once published, or
  `cd tally-connector && pip install -e .` for local install

---

## Dev mocks

- `POST /api/mock/whatsapp/incoming` — simulate WhatsApp invoice send
- `POST /api/mock/tally/voucher` — fake Tally success XML
- `GET /api/mock/whatsapp/send-log` — outbound message log
- `GET /api/infra/call-log` — per-provider telemetry
- Dev panel visible in dashboard when `import.meta.env.DEV`
