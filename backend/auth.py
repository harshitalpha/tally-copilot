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

pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


def hash_password(p: str) -> str:
    return pwd_context.hash(p)


def verify_password(p: str, h: str) -> bool:
    return pwd_context.verify(p, h)


def create_token(user_id: str) -> str:
    exp = datetime.utcnow() + timedelta(hours=EXPIRE_HRS)
    return jwt.encode({"sub": user_id, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
) -> models.User:
    if not x_connector_token:
        raise HTTPException(status_code=401, detail="Missing connector token")
    meta = db.query(models.UserTallyMetadata).filter(
        models.UserTallyMetadata.connector_token == x_connector_token
    ).first()
    if not meta:
        raise HTTPException(status_code=401, detail="Invalid connector token")
    return db.query(models.User).filter(models.User.id == meta.user_id).first()
