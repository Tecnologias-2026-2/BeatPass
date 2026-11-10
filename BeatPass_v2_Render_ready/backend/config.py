"""Configuración por entorno. Ningún secreto se guarda en Git."""
# FLUJO: database.py y security.py leen aquí las variables de entorno.
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_ENV = os.getenv('APP_ENV', 'production').strip().lower()
if APP_ENV == 'local':
    (ROOT / 'instance').mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv('DATABASE_URL') or (f"sqlite:///{ROOT / 'instance' / 'beatpass_v2.db'}" if APP_ENV == 'local' else '')
if not DATABASE_URL:
    raise RuntimeError('Configura DATABASE_URL para PostgreSQL.')
if APP_ENV != 'local' and DATABASE_URL.startswith('sqlite'):
    raise RuntimeError('El despliegue requiere PostgreSQL; SQLite no conserva datos en Render.')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = 'postgresql+psycopg://' + DATABASE_URL[len('postgres://'):]
elif DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = 'postgresql+psycopg://' + DATABASE_URL[len('postgresql://'):]

SECRET_KEY = os.getenv('SECRET_KEY')
if APP_ENV != 'local' and not SECRET_KEY:
    raise RuntimeError('Configura SECRET_KEY en Render antes de desplegar.')
if not SECRET_KEY:
    # Clave persistente para ejecutar pruebas de desarrollo.
    local_key = ROOT / 'instance' / '.local-secret'
    local_key.parent.mkdir(parents=True, exist_ok=True)
    if local_key.exists():
        SECRET_KEY = local_key.read_text(encoding='utf-8').strip()
    else:
        SECRET_KEY = secrets.token_urlsafe(48)
        local_key.write_text(SECRET_KEY, encoding='utf-8')
        try: local_key.chmod(0o600)
        except OSError: pass

# Orígenes de desarrollo; el despliegue utiliza exclusivamente ALLOWED_ORIGINS.
LOCAL_ORIGINS = ['null', 'http://localhost:5500', 'http://127.0.0.1:5500',
                 'http://localhost:8001', 'http://127.0.0.1:8001']
PRODUCTION_ORIGINS = [s.strip().rstrip('/') for s in os.getenv('ALLOWED_ORIGINS', '').split(',') if s.strip()]
if APP_ENV != 'local' and not PRODUCTION_ORIGINS:
    raise RuntimeError('Configura ALLOWED_ORIGINS (URL pública del frontend) en Render.')
ALLOWED_ORIGINS = LOCAL_ORIGINS if APP_ENV == 'local' else PRODUCTION_ORIGINS
TOKEN_EXP_HOURS = 8

# El remitente y el dominio público se definen mediante variables de entorno.

# Fase 2D: bloqueado por defecto fuera de local; nunca es un pago real.
DEMO_CHECKOUT_ENABLED = APP_ENV == 'local' or os.getenv('ENABLE_DEMO_CHECKOUT', 'false').lower() == 'true'

# Fase 2E: desactivado por defecto; las credenciales TEST se configuran manualmente.
# IMPORTANTE: Mercado Pago puede usar APP_USR tanto en test como en producción.
PAYMENT_MODE = os.getenv('PAYMENT_MODE', 'disabled').strip().lower()
if PAYMENT_MODE not in ('disabled', 'mercadopago_sandbox'):
    raise RuntimeError('PAYMENT_MODE solo acepta disabled o mercadopago_sandbox en Fase 2E.')
MP_ACCESS_TOKEN = os.getenv('MP_ACCESS_TOKEN', '').strip()
MP_WEBHOOK_SECRET = os.getenv('MP_WEBHOOK_SECRET', '').strip()
PUBLIC_API_URL = os.getenv('PUBLIC_API_URL', '').strip().rstrip('/')
PUBLIC_FRONTEND_URL = os.getenv('PUBLIC_FRONTEND_URL', '').strip().rstrip('/')
if PAYMENT_MODE == 'mercadopago_sandbox':
    if not MP_ACCESS_TOKEN or not MP_WEBHOOK_SECRET:
        raise RuntimeError('Configura MP_ACCESS_TOKEN (credencial TEST) y MP_WEBHOOK_SECRET.')
    if not (PUBLIC_API_URL.startswith('https://') and PUBLIC_FRONTEND_URL.startswith('https://')):
        raise RuntimeError('Los webhooks y retorno de Mercado Pago requieren PUBLIC_API_URL y PUBLIC_FRONTEND_URL HTTPS.')
