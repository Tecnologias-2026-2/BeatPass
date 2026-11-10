"""Tokens opacos, aleatorios, de un solo uso y guardados únicamente como SHA-256."""
# FLUJO: main.py crea y consume enlaces de verificación/recuperación usando AuthToken.
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from .models import AuthToken

def now():
    return datetime.now(timezone.utc)

def digest(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def make_token(db, user_id: int, purpose: str, hours: int):
    token = secrets.token_urlsafe(40)
    db.add(AuthToken(user_id=user_id, purpose=purpose, token_digest=digest(token),
                     expires_at=now() + timedelta(hours=hours)))
    return token

def is_valid(record):
    if not record or record.used_at:
        return False
    expiry = record.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry > now()
