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

    pairing_code            = Column(String, nullable=True)
    pairing_code_expires_at = Column(DateTime, nullable=True)
    is_paired               = Column(Boolean, default=False)
    paired_at               = Column(DateTime, nullable=True)
    connector_token         = Column(String, nullable=True, unique=True)

    company_name            = Column(String, nullable=True)
    company_gstin           = Column(String, nullable=True)
    purchase_ledger         = Column(String, nullable=True, default="Purchases")
    cgst_ledger_format      = Column(String, nullable=True, default="CGST @ {rate}%")
    sgst_ledger_format      = Column(String, nullable=True, default="SGST @ {rate}%")
    igst_ledger_format      = Column(String, nullable=True, default="IGST @ {rate}%")
    auto_create_ledgers     = Column(Boolean, default=True)
    available_ledgers       = Column(Text, nullable=True)

    last_heartbeat_at       = Column(DateTime, nullable=True)

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
    file_type         = Column(String, nullable=False)
    file_size_bytes   = Column(Integer, nullable=True)
    raw_text          = Column(Text, nullable=True)
    extraction_method = Column(String, nullable=True)
    created_at        = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="documents")


class UserAction(Base):
    __tablename__ = "user_actions_data"

    id          = Column(String, primary_key=True, default=new_uuid)
    user_id     = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    action_type = Column(String, nullable=False)
    status      = Column(String, nullable=False, default="pending", index=True)
    data        = Column(Text, nullable=False, default="{}")
    created_at  = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="actions")
