"""Correo transaccional: Resend por HTTPS; buzón aislado para pruebas automatizadas.
No guarda claves ni tokens en Git; los enlaces temporales no se incluyen en el código.
"""
# FLUJO: main.py genera enlaces con token_service.py y pide enviar correo desde aquí.
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from .config import APP_ENV, ROOT

MAIL_MODE = os.getenv('MAIL_MODE', 'development' if APP_ENV == 'local' else 'resend').strip().lower()
FRONTEND_URL = os.getenv('PUBLIC_FRONTEND_URL', 'http://127.0.0.1:8001' if APP_ENV == 'local' else '').strip().rstrip('/')
MAIL_FROM = os.getenv('MAIL_FROM', '').strip()
RESEND_API_KEY = os.getenv('RESEND_API_KEY', '').strip()

if APP_ENV != 'local':
    if MAIL_MODE != 'resend' or not FRONTEND_URL.startswith('https://') or not MAIL_FROM or not RESEND_API_KEY:
        raise RuntimeError('En Render configura MAIL_MODE=resend, PUBLIC_FRONTEND_URL=https://..., MAIL_FROM y RESEND_API_KEY.')


def send_mail(recipient: str, subject: str, message: str) -> None:
    if MAIL_MODE == 'development' and APP_ENV == 'local':
        box = ROOT / 'instance' / 'dev-mailbox.txt'
        box.parent.mkdir(parents=True, exist_ok=True)
        with box.open('a', encoding='utf-8') as handle:
            handle.write(f'\n--- {subject} ---\nPara: {recipient}\n{message}\n')
        try: box.chmod(0o600)
        except OSError: pass
        return
    if MAIL_MODE != 'resend' or not MAIL_FROM or not RESEND_API_KEY:
        raise RuntimeError('El proveedor de correo no está configurado.')
    data = json.dumps({'from': MAIL_FROM, 'to': [recipient], 'subject': subject, 'text': message}).encode('utf-8')
    req = Request('https://api.resend.com/emails', data=data, headers={
        'Authorization': f'Bearer {RESEND_API_KEY}', 'Content-Type': 'application/json',
        'User-Agent': 'BeatPass/2.1'
    }, method='POST')
    try:
        with urlopen(req, timeout=12) as result:
            if result.status not in (200, 201, 202):
                raise RuntimeError('El proveedor no aceptó el correo.')
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError('No fue posible enviar el correo. Reintenta más tarde.') from exc


def link(page: str, token: str) -> str:
    from urllib.parse import quote
    return f'{FRONTEND_URL}/pages/{page}.html?token={quote(token, safe="")}'
