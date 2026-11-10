"""Fase 2E: límite básico de intentos de acceso por correo.

FLUJO: auth-ui.js -> main.login -> este guardián -> tabla login_throttle.
No reemplaza WAF/IP rate limiting de producción. Se almacena hash HMAC, no correo.
"""
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .config import SECRET_KEY
from .models import LoginThrottle

MAX_FAILURES = 8
WINDOW = timedelta(minutes=15)


def _key(email: str) -> str:
    return hmac.new(SECRET_KEY.encode(), email.strip().casefold().encode(), hashlib.sha256).hexdigest()


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def check_login(db: Session, email: str):
    entry = db.get(LoginThrottle, _key(email))
    if entry and _utc(entry.window_started) + WINDOW > datetime.now(timezone.utc) and entry.attempts >= MAX_FAILURES:
        raise HTTPException(429, 'Demasiados intentos. Prueba en 15 minutos.')


def bad_login(db: Session, email: str):
    key = _key(email)
    entry = db.get(LoginThrottle, key)
    current = datetime.now(timezone.utc)
    if entry is None:
        db.add(LoginThrottle(key=key, attempts=1, window_started=current))
    elif _utc(entry.window_started) + WINDOW <= current:
        entry.attempts = 1
        entry.window_started = current
    else:
        entry.attempts += 1
    db.commit()


def good_login(db: Session, email: str):
    entry = db.get(LoginThrottle, _key(email))
    if entry:
        db.delete(entry)
        db.commit()
