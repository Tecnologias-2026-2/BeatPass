"""Comandos de mantenimiento y aprovisionamiento controlado de cuentas."""
# FLUJO: La terminal crea el primer administrador; guarda su rol en models.py vía database.py.
import argparse
import os
import getpass
import sys
from sqlalchemy import select
from .database import SessionLocal
from .main import init_schema
from .models import User, UserRole, utc_now
from .security import hash_password


def _read_password(prompt: str, visible: bool) -> str:
    if visible:
        return input(prompt)
    try:
        return getpass.getpass(prompt)
    except (EOFError, KeyboardInterrupt) as exc:
        raise SystemExit('\nEntrada cancelada. Prueba desde CMD o PowerShell interactivo.') from exc


def create_admin(email: str, visible: bool = False):
    init_schema()
    email = email.strip().casefold()
    if not email or '@' not in email:
        raise SystemExit('Introduce un correo válido con --email.')
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == email)) is not None:
            raise SystemExit('El correo ya existe. Inicia sesión como administrador e invítalo desde Solicitudes y accesos.')
        if not sys.stdin.isatty():
            raise SystemExit('Ejecuta este comando en una ventana interactiva de CMD o PowerShell.')
        fullname = input('Nombre del administrador: ').strip()
        if len(fullname) < 2:
            raise SystemExit('Nombre demasiado corto.')
        if visible:
            print('ADVERTENCIA: lo que escribas será visible en pantalla. Hazlo solo en un computador privado.')
        else:
            print('AVISO: la contraseña se escribe aunque NO veas letras, puntos ni asteriscos.')
            print('Escribe la contraseña y pulsa ENTER. Es normal que el cursor parezca inmóvil.')
            print('Si tu terminal no acepta esa entrada, vuelve a ejecutar con --visible-password.')
        try:
            password = _read_password('Contraseña (mínimo 12 caracteres): ', visible)
            confirmation = _read_password('Confirmar contraseña: ', visible)
        except KeyboardInterrupt as exc:
            raise SystemExit('\nOperación cancelada.') from exc
        if len(password) < 12:
            raise SystemExit('La contraseña debe tener al menos 12 caracteres.')
        if password != confirmation:
            raise SystemExit('Las contraseñas no coinciden. No se creó la cuenta.')
        user = User(email=email, fullname=fullname, password_hash=hash_password(password),
                    status='active', email_verified_at=utc_now())
        user.roles.extend([UserRole(role_code='cliente'), UserRole(role_code='administracion')])
        db.add(user)
        db.commit()
        print('Administrador creado correctamente. La contraseña se guardó solo como hash Argon2id.')
        print('Nota: este alta inicial es un proceso controlado. Las cuentas administrativas siguientes se invitan por correo.')



def bootstrap_render_admin():
    """Crear una sola cuenta administrativa usando secretos de entorno de Render.

    No modifica usuarios existentes y no escribe secretos en el repositorio.
    """
    if os.getenv('BEATPASS_BOOTSTRAP_ADMIN_ENABLED', '').casefold() != 'true':
        return
    from .config import APP_ENV, DATABASE_URL
    if APP_ENV == 'local' or not DATABASE_URL.startswith('postgresql'):
        raise SystemExit('El aprovisionamiento requiere un despliegue PostgreSQL.')
    email = os.getenv('BEATPASS_BOOTSTRAP_ADMIN_EMAIL', '').strip().casefold()
    fullname = os.getenv('BEATPASS_BOOTSTRAP_ADMIN_NAME', '').strip()
    password = os.getenv('BEATPASS_BOOTSTRAP_ADMIN_PASSWORD', '')
    if not email or '@' not in email or len(fullname) < 2 or len(password) < 12:
        raise SystemExit('Falta configurar una cuenta administrativa válida y su secreto.')
    init_schema()
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            if any(role.role_code == 'administracion' for role in existing.roles):
                print('Aprovisionamiento ya realizado. No hay cambios.')
                return
            raise SystemExit('Ese correo ya pertenece a otra cuenta; se requiere una invitación administrativa.')
        user = User(email=email, fullname=fullname, password_hash=hash_password(password),
                    status='active', email_verified_at=utc_now())
        user.roles.extend([UserRole(role_code='cliente'), UserRole(role_code='administracion')])
        db.add(user)
        db.commit()
        print('Cuenta administrativa inicial creada. Retira el secreto de aprovisionamiento de Render.')


def expire_holds():
    # FLUJO: programador de tareas -> cli expire-holds -> orders.expire_orders() -> inventory.held.
    from .orders import expire_orders
    init_schema()
    with SessionLocal() as db:
        loops = 0
        while expire_orders(db):
            loops += 1
            if loops >= 1000:
                raise SystemExit('Demasiadas reservas para limpiar de una sola vez; revisa el job.')
        print('Reservas vencidas revisadas.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Administración local segura de BeatPass')
    parser.add_argument('command', choices=['create-admin', 'expire-holds', 'bootstrap-render-admin'])
    parser.add_argument('--email')
    parser.add_argument('--visible-password', action='store_true',
                        help='Muestra la contraseña mientras escribes; solo si getpass no funciona en CMD.')
    options = parser.parse_args()
    if options.command == 'expire-holds':
        expire_holds()
    elif options.command == 'bootstrap-render-admin':
        bootstrap_render_admin()
    else:
        if not options.email:
            parser.error('create-admin requiere --email')
        create_admin(options.email, visible=options.visible_password)
