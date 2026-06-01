"""Envelope encryption for stored provider credentials.

Key comes from INFRA_MASTER_KEY env (a urlsafe base64-encoded 32-byte string).
In dev, if unset we generate a deterministic dev key from a sentinel so SQLite
state survives restarts. NEVER use the dev fallback in production.
"""
import os, base64, hashlib
from cryptography.fernet import Fernet, InvalidToken


_DEV_SENTINEL = "tally-copilot-dev-fallback"


def _resolve_key() -> bytes:
    raw = os.getenv("INFRA_MASTER_KEY")
    if raw:
        return raw.encode()
    # Dev fallback — deterministic so encrypted rows still decrypt across restarts.
    digest = hashlib.sha256(_DEV_SENTINEL.encode()).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_resolve_key())


def encrypt(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(ciphertext: str) -> str:
    try:
        return _fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as e:
        raise RuntimeError(
            "Could not decrypt provider config. INFRA_MASTER_KEY does not match "
            "the key used to encrypt this row."
        ) from e


def is_dev_key() -> bool:
    return not os.getenv("INFRA_MASTER_KEY")
