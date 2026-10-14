"""Field-level encryption for sensitive numbers (bank account numbers).

Set DATA_KEY in .env to a Fernet key:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
Keep it safe and never change it after data is stored, or encrypted values can no longer be read.
If DATA_KEY is missing, a key is derived from JWT_SECRET (acceptable for development only).
"""
import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

from .config import settings

log = logging.getLogger("mirai.crypto")


def _key() -> bytes:
    k = os.getenv("DATA_KEY", "").strip()
    if k:
        return k.encode()
    if settings.ENV == "production":
        log.warning("DATA_KEY is not set – deriving the encryption key from JWT_SECRET. Set DATA_KEY in .env.")
    return base64.urlsafe_b64encode(hashlib.sha256(("mirai-data:" + settings.JWT_SECRET).encode()).digest())


_f = Fernet(_key())


def encrypt(value: str | None) -> str | None:
    return _f.encrypt(value.encode()).decode() if value else None


def decrypt(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _f.decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def mask(value: str | None, keep: int = 4) -> str | None:
    if not value:
        return None
    return "XXXX" + value[-keep:]
