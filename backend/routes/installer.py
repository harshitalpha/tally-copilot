"""Public installer endpoints — no auth (the Tally laptop has no token yet).

Serves:
  GET /install.ps1         Windows PowerShell bootstrap (one-liner install)
  GET /install.sh          macOS/Linux bootstrap
  GET /connector/<file>    raw connector source (connector.py, tally_xml.py)

The bootstrap scripts bake in THIS backend's public URL automatically, so the
connector's .env is pre-configured — no manual editing on the client machine.
"""
import pathlib
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import PlainTextResponse, Response

router = APIRouter()

_CONNECTOR_DIR = pathlib.Path(__file__).resolve().parent.parent / "static" / "connector"
_ALLOWED_FILES = {"connector.py", "tally_xml.py"}


def _base_url(request: Request) -> str:
    """Public base URL, honoring Railway's TLS-terminating proxy."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", request.url.netloc)
    return f"{proto}://{host}"


@router.get("/connector/{filename}")
def connector_file(filename: str):
    if filename not in _ALLOWED_FILES:
        raise HTTPException(404, "Not found")
    path = _CONNECTOR_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Not found")
    return PlainTextResponse(path.read_text(), media_type="text/x-python")


_PS1 = r'''# Tally Co-pilot Connector - Windows installer
# Run in PowerShell:  irm __BACKEND__/install.ps1 | iex
$ErrorActionPreference = "Stop"
$BACKEND = "__BACKEND__"
$DIR = "$env:USERPROFILE\tally-copilot-connector"

Write-Host "=== Tally Co-pilot Connector installer ===" -ForegroundColor Cyan
Write-Host "Backend: $BACKEND"

# 1. Ensure Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found - installing via winget..."
    try {
        winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    } catch {
        Write-Host "Could not auto-install Python." -ForegroundColor Red
        Write-Host "Install it from https://python.org (tick 'Add Python to PATH'), then re-run this."
        exit 1
    }
}

# 2. Folder
New-Item -ItemType Directory -Force -Path $DIR | Out-Null

# 3. Download connector source
Write-Host "Downloading connector..."
Invoke-WebRequest "$BACKEND/connector/connector.py" -OutFile "$DIR\connector.py" -UseBasicParsing
Invoke-WebRequest "$BACKEND/connector/tally_xml.py" -OutFile "$DIR\tally_xml.py" -UseBasicParsing

# 4. Python packages
Write-Host "Installing Python packages..."
python -m pip install --quiet --upgrade pip
python -m pip install --quiet requests python-dotenv

# 5. Default config (don't clobber an existing .env on re-run)
if (-not (Test-Path "$DIR\.env")) {
@"
BACKEND_URL=$BACKEND
TALLY_URL=http://localhost:9000
POLL_INTERVAL_SECONDS=10
"@ | Set-Content "$DIR\.env"
}

# 6. Double-click launchers
"@echo off`r`ncd /d ""$DIR""`r`npython connector.py test`r`npause" | Set-Content "$DIR\test-connection.bat"
"@echo off`r`ncd /d ""$DIR""`r`npython connector.py`r`npause" | Set-Content "$DIR\start-connector.bat"

Write-Host ""
Write-Host "Installed to: $DIR" -ForegroundColor Green
Write-Host "Next steps:"
Write-Host "  1) Double-click  test-connection.bat   (checks Tally + backend)"
Write-Host "  2) Generate a pairing code in the dashboard"
Write-Host "  3) Double-click  start-connector.bat    (pair + run)"
'''


_SH = r'''#!/usr/bin/env bash
# Tally Co-pilot Connector - macOS/Linux installer
# Run:  curl -fsSL __BACKEND__/install.sh | bash
set -e
BACKEND="__BACKEND__"
DIR="$HOME/tally-copilot-connector"

echo "=== Tally Co-pilot Connector installer ==="
echo "Backend: $BACKEND"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 not found. Install it from https://python.org and re-run."
  exit 1
fi

mkdir -p "$DIR"
echo "Downloading connector..."
curl -fsSL "$BACKEND/connector/connector.py" -o "$DIR/connector.py"
curl -fsSL "$BACKEND/connector/tally_xml.py" -o "$DIR/tally_xml.py"

echo "Installing Python packages..."
python3 -m pip install --quiet --upgrade pip
python3 -m pip install --quiet requests python-dotenv

if [ ! -f "$DIR/.env" ]; then
cat > "$DIR/.env" <<EOF
BACKEND_URL=$BACKEND
TALLY_URL=http://localhost:9000
POLL_INTERVAL_SECONDS=10
EOF
fi

echo ""
echo "Installed to: $DIR"
echo "Next:"
echo "  cd \"$DIR\""
echo "  python3 connector.py test    # checks Tally + backend"
echo "  python3 connector.py         # pair + run"
'''


@router.get("/install.ps1")
def install_ps1(request: Request):
    return PlainTextResponse(_PS1.replace("__BACKEND__", _base_url(request)),
                             media_type="text/plain")


@router.get("/install.sh")
def install_sh(request: Request):
    return PlainTextResponse(_SH.replace("__BACKEND__", _base_url(request)),
                             media_type="text/plain")
