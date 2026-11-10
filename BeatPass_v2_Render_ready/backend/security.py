"""Hash Argon2id y JWT HS256; roles siempre verificados contra la BD."""
# FLUJO: main.py y profile.py llaman funciones para hash de contraseña y JWT.
from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher, exceptions
from .config import SECRET_KEY, TOKEN_EXP_HOURS

hasher = PasswordHasher()

def hash_password(password: str) -> str:
    return hasher.hash(password)

def verify_password(stored: str, candidate: str) -> bool:
    try:
        return hasher.verify(stored, candidate)
    except (exceptions.VerifyMismatchError, exceptions.VerificationError, exceptions.InvalidHashError):
        return False

def issue_token(user_id: int, token_version: int = 0) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': str(user_id), 'ver': token_version, 'iat': now, 'exp': now + timedelta(hours=TOKEN_EXP_HOURS),
                       'iss': 'beatpass-v2', 'aud': 'beatpass-frontend'}, SECRET_KEY, algorithm='HS256')

def decode_token(token: str) -> tuple[int, int]:
    payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'],
                         issuer='beatpass-v2', audience='beatpass-frontend',
                         options={'require': ['sub', 'iat', 'exp', 'iss', 'aud']})
    return int(payload['sub']), int(payload.get('ver', 0))
