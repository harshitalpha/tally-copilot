# Tally Co-pilot — Working Notes

> Full system spec: see [`complete_architecture.md`](./complete_architecture.md).
> This file is the short, important stuff to keep in working memory.

---

## What this is

Users register a WhatsApp number once. Any PDF/image invoice they send from that number is:
**downloaded → AI-extracted (Claude) → GST-validated → pushed to Tally as a Purchase voucher → confirmed back via WhatsApp.**

No human approval. Unregistered numbers get a "please register" reply.

---

## Project layout

```
tally-copilot/
├── backend/           FastAPI + SQLite, AI pipeline, all routes
├── frontend/          React + Vite + Tailwind v3, read-only dashboard
└── tally-connector/   Polling daemon that runs on the user's Tally machine
```

The DB (`backend/tally_copilot.db`) is git-ignored / disposable in dev — delete to reset.

---

## Critical invariant: action status flow

```
pending → processing → pending_sync → synced
                     → failed
```

- `pending` / `processing` — pipeline owns it
- `pending_sync` — **connector** polls for these and pushes to Tally
- `synced` / `failed` — terminal; triggers WhatsApp confirmation/failure message

WhatsApp confirmation is sent by the **sync-complete** route (after Tally returns voucher_id), NOT by the pipeline. The pipeline only sends failure messages when extraction itself fails.

---

## Action data payload (`UserAction.data` JSON)

This is the contract between pipeline, connector, and UI. All four parties read/write it.

```json
{
  "document_id": "uuid",
  "source": "whatsapp | dashboard",
  "sender_phone": "+91… | null",
  "extraction_method": "pdfplumber | document_ai | null",
  "extracted_invoice": { /* see complete_architecture.md §5 */ },
  "validation_errors": [],
  "validation_warnings": [],
  "tally_voucher_id": "string | null",
  "tally_error": "string | null"
}
```

---

## Auth

- **User**: JWT `Authorization: Bearer <token>` (HS256, 24h expiry).
- **Connector**: `X-Connector-Token: <token>` — issued on `POST /api/tally/pair`. Each `generate-pairing-code` call **invalidates the previous connector token**; the connector must re-pair.

---

## How to run (3 terminals)

```bash
# T1 — backend
cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8000

# T2 — frontend
cd frontend && npm run dev    # http://localhost:5173

# T3 — connector (after generating pairing code in dashboard)
cd tally-connector && python connector.py
```

**Required env** (`backend/.env`):
```
APP_ENV=development
ANTHROPIC_API_KEY=sk-ant-...      # without this the LLM extract step fails -> every invoice ends up `failed`
JWT_SECRET=anything-for-dev
WHATSAPP_VERIFY_TOKEN=anything-for-dev
```

---

## Environment quirks (Python 3.14 macOS)

- **`sqlalchemy>=2.0.36`** — older versions crash on import on 3.14 (`__firstlineno__` symbol collision).
- **`bcrypt==4.0.1`** — bcrypt 4.1+ breaks passlib's wrap-bug detection with `ValueError: password cannot be longer than 72 bytes`.
- **Node**: not installed by default; `brew install node` lands at `/opt/homebrew/bin/node`.
- **npm**: global `~/.npmrc` has legacy `_auth` form that modern npm rejects. Workaround: `env HOME=/tmp/empty-dir npm ...` + project-local `.npmrc` with `registry=https://registry.npmjs.org/`.

---

## Known fixes already applied (don't re-introduce)

- **Connector error check**: spec had `if "ERRORS>0" in r.text` — but mock Tally returns `<ERRORS>0</ERRORS>` which contains that substring. Fixed to regex `<ERRORS>(\d+)</ERRORS>` checking for non-zero (`tally-connector/connector.py:_has_error`).
- **ProtectedRoute**: uses react-router's `useLocation` (not `window.location.pathname`) and re-fetches `/me` on path change — needed so an already-onboarded user landing on `/onboarding` redirects to `/dashboard`.

---

## Dev mocks (only loaded when `APP_ENV=development`)

- `POST /api/mock/whatsapp/incoming` — simulate inbound WhatsApp message (form: `file`, `sender_phone`).
- `POST /api/mock/tally/voucher` — returns a fake success XML; set as `TALLY_URL` in connector `.env`.
- `GET /api/mock/whatsapp/send-log` — every outbound WA message held in-memory.
- Dashboard's `MockPanel` (dev only) wraps these.

OTPs for WhatsApp registration are returned in the response body as `dev_otp` when `APP_ENV=development`.

---

## Build/test order (if rebuilding)

`backend skeleton → auth routes → extractor+validator → mock → tally_connector+onboarding routes → documents+pipeline → whatsapp webhook+sender → actions route → connector script → frontend.`

End-to-end smoke test lives in `complete_architecture.md §13`.
