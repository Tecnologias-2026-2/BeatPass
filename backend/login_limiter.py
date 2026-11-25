"""Fase 2E: límite de intentos de acceso por correo y por IP de origen.

FLUJO: auth-ui.js -> main.login -> este guardián -> tabla login_throttle.
No reemplaza WAF/IP rate limiting de producción. Se almacena hash HMAC, no correo.
El límite por correo solo frena intentos FALLIDOS: una contraseña correcta nunca
queda bloqueada, así que un tercero no puede dejar fuera al titular conociendo su correo.
"""
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .config import SECRET_KEY
from .models import LoginThrottle

MAX_FAILURES = 8
MAX_IP_FAILURES = 40
WINDOW = timedelta(minutes=15)


def _key(email: str) -> str:
    return hmac.new(SECRET_KEY.encode(), email.strip().casefold().encode(), hashlib.sha256).hexdigest()


def _ip_key(address: str) -> str:
    return hmac.new(SECRET_KEY.encode(), ('ip:' + address).encode(), hashlib.sha256).hexdigest()


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _blocked(entry, limit: int) -> bool:
    return bool(entry and entry.attempts >= limit
                and _utc(entry.window_started) + WINDOW > datetime.now(timezone.utc))


def check_login(db: Session, email: str, client_ip: str | None = None):
    if _blocked(db.get(LoginThrottle, _key(email)), MAX_FAILURES):
        raise HTTPException(429, 'Demasiados intentos. Prueba en 15 minutos.')
    # Límite de respaldo por conexión: frena el bombardeo a muchas cuentas desde una IP.
    if client_ip and _blocked(db.get(LoginThrottle, _ip_key(client_ip)), MAX_IP_FAILURES):
        raise HTTPException(429, 'Demasiados intentos desde esta conexión. Prueba en 15 minutos.')


def _count(db: Session, key: str) -> int:
    entry = db.get(LoginThrottle, key)
    current = datetime.now(timezone.utc)
    if entry is None:
        db.add(LoginThrottle(key=key, attempts=1, window_started=current))
        return 1
    if _utc(entry.window_started) + WINDOW <= current:
        entry.attempts = 1
        entry.window_started = current
        return 1
    entry.attempts += 1
    return entry.attempts


def bad_login(db: Session, email: str, client_ip: str | None = None):
    attempts = _count(db, _key(email))
    if client_ip:
        _count(db, _ip_key(client_ip))
    db.commit()
    if attempts > MAX_FAILURES:
        raise HTTPException(429, 'Demasiados intentos. Prueba en 15 minutos.')


def good_login(db: Session, email: str):
    entry = db.get(LoginThrottle, _key(email))
    if entry:
        db.delete(entry)
        db.commit()
