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
