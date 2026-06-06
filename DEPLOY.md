# Deploying Tally Co-pilot

Two parts:

- **Part A — Deploy the backend to Railway** (one time, ~10 min)
- **Part B — Connect a Tally laptop** (one line, ~2 min per laptop)

---

## Part A — Deploy the backend (Railway)

### 1. Push the code to GitHub

Railway deploys from your GitHub repo. Make sure your latest code is pushed:

```bash
git push origin main
```

### 2. Create the Railway project

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Pick **`harshitalpha/tally-copilot`**
3. Railway reads `railway.toml` and builds `backend/Dockerfile` automatically.

### 3. Add a Volume (so data survives redeploys) — IMPORTANT

Railway wipes the container filesystem on every deploy. Without a volume, **every
user, pairing, and provider config resets on each redeploy.**

1. Service → **Variables** tab is for env. Go to **Settings → Volumes** → **New Volume**
2. Mount path: **`/data`**

### 4. Set environment variables

Service → **Variables** → paste these (use the **Raw Editor** for speed):

```
APP_ENV=production
DATABASE_URL=sqlite:////data/tally_copilot.db
UPLOAD_DIR=/data/uploads

JWT_SECRET=<generate — see below>
INFRA_MASTER_KEY=<generate — see below>

GEMINI_API_KEY=<your Gemini key>
GEMINI_MODEL=models/gemma-4-31b-it

RESEND_API_KEY=<your Resend key, or leave unset for in-memory email log>
RESEND_FROM_EMAIL=noreply@yourdomain.com

APP_URL=https://<your-frontend>.vercel.app
CORS_ORIGINS=https://<your-frontend>.vercel.app
```

Notes:
- **`DATABASE_URL` has four slashes** (`sqlite:////data/...`) — that's an absolute path. Three slashes is a relative path and will NOT land on the volume.
- **`INFRA_MASTER_KEY` must never change** once set, or stored provider credentials become undecryptable. Treat it like a password.
- If you skip `RESEND_API_KEY`, OTP/reset emails are logged to the server instead of sent — fine for testing, not for real users.

**Generate the two secrets** (run locally, paste the output):

```bash
# JWT_SECRET
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# INFRA_MASTER_KEY (must be a Fernet key — urlsafe base64, 32 bytes)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 5. Generate a public domain

Service → **Settings → Networking → Generate Domain**.

You'll get something like `https://tally-copilot-production.up.railway.app`.

### 6. Verify it's up

```bash
curl https://<your-url>/health
# {"status":"ok","env":"production","version":"0.2.0"}
```

That URL is now also your **installer host** (Part B).

---

## Part B — Connect a Tally laptop (the one-liner)

On the Windows laptop that runs Tally:

### 1. Make sure Tally accepts HTTP requests

In Tally: **Gateway of Tally → F1 (Help) → Settings → Connectivity → Client/Server
configuration** (or **F12 → Advanced Configuration** in older builds):

- **TallyPrime acts as**: `Both`
- **Enable ODBC / Port**: `9000`

Keep Tally open with your company loaded.

### 2. Install the connector — one line

Open **PowerShell** and paste:

```powershell
irm https://<your-url>/install.ps1 | iex
```

That single command:
- installs Python (via winget) if it's missing,
- downloads the connector,
- installs its Python packages,
- writes a `.env` already pointing at your backend and at `localhost:9000`,
- drops two double-click launchers in `%USERPROFILE%\tally-copilot-connector\`.

> macOS/Linux test laptop instead? Use `curl -fsSL https://<your-url>/install.sh | bash`.

### 3. Check the connection

Double-click **`test-connection.bat`**. It confirms it can reach both Tally and the
backend, and lists the companies it found in Tally.

### 4. Pair and run

1. In the web dashboard: **Settings → Generate pairing code**.
2. Double-click **`start-connector.bat`** and enter the code when prompted.
3. It pairs, detects your company, and starts polling. Leave it running.

That's it. Uploads in the dashboard now flow into Tally as Purchase vouchers.

---

## Updating later

- **Backend code change** → `git push origin main`; Railway auto-redeploys.
- **Connector code change** → re-run the one-liner on the laptop. It re-downloads
  `connector.py` / `tally_xml.py` but **keeps the existing `.env`** (won't clobber config).
  - Reminder: the installer serves `backend/static/connector/`. If you edit the
    connector under `tally-connector/`, copy the two files into
    `backend/static/connector/` before pushing, or the laptops get the old version.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `irm ... \| iex` blocked | Run PowerShell as Administrator, or `Set-ExecutionPolicy -Scope Process Bypass` first. |
| `test-connection.bat` can't reach Tally | Tally not open, company not loaded, or port ≠ 9000. Re-check step B1. |
| Vouchers stuck in `pending_sync` | Connector not running — double-click `start-connector.bat`. |
| Users/config vanished after deploy | Volume not mounted at `/data`, or `DATABASE_URL` doesn't have 4 slashes. |
| OTP email never arrives | `RESEND_API_KEY` unset → check Railway logs for the logged OTP, or set the key. |
