from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, SessionLocal
import models, os
from dotenv import load_dotenv

load_dotenv()
from routes import auth, onboarding, actions, documents, whatsapp, tally_connector, infra, settings, installer
from infra.seed import seed_if_empty

models.Base.metadata.create_all(bind=engine)

_db = SessionLocal()
try:
    seed_if_empty(_db)
finally:
    _db.close()

app = FastAPI(title="Tally Co-pilot", version="0.2.0")

# CORS_ORIGINS is a comma-separated list; defaults to local dev frontend.
# In prod set e.g. CORS_ORIGINS=https://your-frontend.vercel.app,http://localhost:5173
_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,             prefix="/api/auth")
app.include_router(onboarding.router,       prefix="/api/onboarding")
app.include_router(actions.router,          prefix="/api/actions")
app.include_router(documents.router,        prefix="/api/documents")
app.include_router(whatsapp.router,         prefix="/api/whatsapp")
app.include_router(tally_connector.router,  prefix="/api/tally")
app.include_router(infra.router,            prefix="/api/infra")
app.include_router(settings.router,         prefix="/api/settings")
app.include_router(installer.router)  # root-level: /install.ps1, /install.sh, /connector/*

if os.getenv("APP_ENV") == "development":
    from routes import mock
    app.include_router(mock.router, prefix="/api/mock")


@app.get("/health")
def health():
    return {"status": "ok", "env": os.getenv("APP_ENV", "production"), "version": "0.2.0"}
