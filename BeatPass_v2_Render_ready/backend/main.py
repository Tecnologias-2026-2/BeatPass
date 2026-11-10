"""API central BeatPass 2E: cuentas, sesiones, roles y registro de rutas de eventos/pagos."""
# FLUJO: pages/login.html y register.html -> js/pages/auth-ui.js -> api.js -> main.py -> models.py.
from contextlib import asynccontextmanager
import re
from jwt import InvalidTokenError
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, inspect, exists
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .config import ALLOWED_ORIGINS, APP_ENV
from .database import engine, Base, get_db, SessionLocal
from .models import User, Role, UserRole, OrganizerProfile, OrganizerApplication, AuthToken, AdminInvitation, AuditLog, LoginThrottle
from .event_models import Event, EventRevision, EventCover
from .inventory_models import TicketInventory, CartItem
from .order_models import PurchaseOrder, PurchaseOrderItem, IssuedTicket, PaymentAttempt
from .security import hash_password, verify_password, issue_token, decode_token
from .token_service import make_token, digest, is_valid, now
from .email_service import send_mail, link
from .schemas import RegisterBody, LoginBody, ReviewBody, EmailBody, TokenBody, PasswordResetBody, InvitationAcceptBody

ROLE_LABELS = {'cliente': 'Cliente', 'organizador': 'Organizador', 'administracion': 'Administración', 'acceso': 'Personal de acceso'}

def init_schema():
    # Compatibilidad con esquemas de versiones anteriores.
    # Solo en la transición inicial se consideran verificados los usuarios legados.
    inspector = inspect(engine)
    if inspector.has_table('users'):
        columns = {col['name'] for col in inspector.get_columns('users')}
        with engine.begin() as conn:
            if 'email_verified_at' not in columns:
                conn.exec_driver_sql('ALTER TABLE users ADD COLUMN email_verified_at TIMESTAMP')
                # Conservamos el estado de cuentas anteriores durante actualizaciones compatibles.
                # En producción no damos por verificado un correo sin haber confirmado su titularidad.
                if APP_ENV == 'local':
                    conn.exec_driver_sql('UPDATE users SET email_verified_at = created_at')
            if 'token_version' not in columns:
                conn.exec_driver_sql('ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0')
    # En Render la creación y actualización del esquema corresponde a Alembic.
    # Las pruebas de desarrollo utilizan create_all; el despliegue usa Alembic.
    if APP_ENV != 'local' and not inspector.has_table('alembic_version'):
        raise RuntimeError('Ejecuta python -m alembic upgrade head antes de iniciar la API.')
    if APP_ENV == 'local':
        Base.metadata.create_all(bind=engine)
    # Compatible con BD 2B: las revisiones antiguas no tenían capacidad.
    # Se importan como cero, nunca se inventa inventario vendible.
    from .cart import sync_inventory
    with SessionLocal() as db:
        missing_inventory = select(Event).where(Event.published_revision_id.is_not(None),
            ~exists(select(TicketInventory.id).where(TicketInventory.revision_id == Event.published_revision_id)))
        for event in db.scalars(missing_inventory).all():
            revision = db.get(EventRevision, event.published_revision_id)
            if revision and revision.status == 'approved':
                sync_inventory(db, event, revision)
        for code, label in ROLE_LABELS.items():
            if not db.get(Role, code): db.add(Role(code=code, label=label))
        db.commit()

@asynccontextmanager
async def lifespan(_):
    init_schema()
    yield

app = FastAPI(title='BeatPass v2 API', version='2.6.0-2E', lifespan=lifespan,
              docs_url='/docs' if APP_ENV == 'local' else None,
              redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=False,
                   allow_methods=['GET','POST','PUT','PATCH','DELETE'], allow_headers=['Authorization','Content-Type'])

def roles(user: User) -> list[str]:
    return [rel.role_code for rel in user.roles]

def user_view(user: User) -> dict:
    return {'id': user.id, 'email': user.email, 'fullname': user.fullname,
            'email_verified': user.email_verified_at is not None,
            'roles': roles(user), 'organizer_status': user.organizer_profile.status if user.organizer_profile else None}

def authenticated_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Debes iniciar sesión.')
    try:
        user_id, token_version = decode_token(authorization[7:])
    except (ValueError, InvalidTokenError) as exc:
        # El error original nunca se filtra al navegador.
        raise HTTPException(401, 'Sesión inválida o expirada.') from exc
    user = db.get(User, user_id)
    if not user or user.status != 'active' or user.token_version != token_version or user.email_verified_at is None:
        raise HTTPException(401, 'La cuenta no está disponible.')
    return user

def require_admin(user: User = Depends(authenticated_user)) -> User:
    if 'administracion' not in roles(user):
        raise HTTPException(403, 'Se necesita autorización de administración.')
    return user

@app.get('/api/health')
def health():
    return {'status': 'ok', 'stage': '2E'}

# Registro: auth-ui.js -> api.register() -> User + token_service.py + email_service.py.
@app.post('/api/auth/register', status_code=201)
def register(body: RegisterBody, db: Session = Depends(get_db)):
    email = _normalize_email(body.email)
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(409, 'Ya existe una cuenta con ese correo.')
    if body.profile == 'organizador' and not (body.organization or '').strip():
        raise HTTPException(422, 'Indica el nombre del organizador o empresa.')
    if body.profile == 'organizador' and not all([(body.phone or '').strip(), (body.city or '').strip(), (body.description or '').strip()]):
        raise HTTPException(422, 'Completa la información adicional del organizador.')
    user = User(email=email, fullname=body.fullname, password_hash=hash_password(body.password), status='active')
    user.roles.append(UserRole(role_code='cliente'))
    if body.profile == 'organizador':
        profile = OrganizerProfile(display_name=body.organization.strip(),phone=body.phone.strip(),
                                   city=body.city.strip(),description=body.description.strip(),status='pending')
        profile.applications.append(OrganizerApplication(status='pending'))
        user.organizer_profile = profile
    db.add(user)
    try:
        db.flush()
        verification_token = make_token(db, user.id, 'email_verification', 24)
        send_mail(email, 'Confirma tu correo en BeatPass',
                  f'Confirma tu cuenta en las próximas 24 horas:\n{link("verify-email", verification_token)}\nSi no creaste la cuenta, ignora este correo.')
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'Ya existe una cuenta con ese correo.') from exc
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(503, 'No se pudo enviar el correo de verificación. Reintenta el registro más tarde.') from exc
    db.refresh(user)
    return {'message': 'Cuenta creada. Revisa tu correo para verificarla. La solicitud de organizador seguirá pendiente de aprobación.' if body.profile == 'organizador' else 'Cuenta creada. Verifica tu correo antes de iniciar sesión.',
            'user': user_view(user)}

# Login: auth-ui.js -> api.login() -> validación de JWT en security.py.
@app.post('/api/auth/login')
def login(body: LoginBody, db: Session = Depends(get_db)):
    from .login_limiter import check_login, bad_login, good_login
    check_login(db, body.email)
    user = db.scalar(select(User).where(User.email == body.email.strip().casefold()))
    if not user or user.status != 'active' or not verify_password(user.password_hash, body.password):
        bad_login(db, body.email)
        raise HTTPException(401, 'Correo o contraseña incorrectos.')
    good_login(db, body.email)
    if user.email_verified_at is None:
        raise HTTPException(403, 'Debes verificar tu correo antes de iniciar sesión. Revisa tu bandeja o solicita otro enlace.')
    available = roles(user)
    if body.profile not in available:
        if body.profile == 'organizador' and user.organizer_profile and user.organizer_profile.status == 'pending':
            raise HTTPException(403, 'Tu solicitud de organizador sigue pendiente. Puedes entrar como cliente.')
        raise HTTPException(403, 'Tu cuenta no tiene permisos para este tipo de acceso.')
    return {'access_token': issue_token(user.id, user.token_version), 'token_type': 'bearer', 'user': user_view(user)}

@app.get('/api/auth/me')
def me(user: User = Depends(authenticated_user)):
    return user_view(user)

@app.get('/api/organizers/me')
def organizer_status(user: User = Depends(authenticated_user)):
    profile = user.organizer_profile
    return {'status': profile.status, 'organization': profile.display_name} if profile else {'status': 'not_requested'}

@app.get('/api/admin/applications')
def pending_applications(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    applications = db.scalars(select(OrganizerApplication).where(OrganizerApplication.status == 'pending').order_by(OrganizerApplication.submitted_at)).all()
    return [{'id': a.id, 'organization': a.profile.display_name, 'fullname': a.profile.user.fullname,
             'email': a.profile.user.email, 'city': a.profile.city, 'phone': a.profile.phone,
             'description': a.profile.description, 'submitted_at': a.submitted_at.isoformat()}
            for a in applications]

def review(application_id: int, decision: str, body: ReviewBody, db: Session, admin: User):
    application = db.get(OrganizerApplication, application_id)
    if not application: raise HTTPException(404, 'Solicitud no encontrada.')
    if application.status != 'pending': raise HTTPException(409, 'Esta solicitud ya fue revisada.')
    if application.profile.user_id == admin.id:
        raise HTTPException(403, 'No puedes aprobar tu propia solicitud.')
    if decision == 'rejected' and not body.reason.strip():
        raise HTTPException(422, 'Indica el motivo del rechazo.')
    application.status = decision
    application.reason = body.reason.strip() or None
    application.reviewer_id = admin.id
    application.reviewed_at = datetime.now(timezone.utc)
    application.profile.status = 'approved' if decision == 'approved' else 'rejected'
    if decision == 'approved' and 'organizador' not in roles(application.profile.user):
        db.add(UserRole(user_id=application.profile.user_id, role_code='organizador'))
    db.add(AuditLog(actor_id=admin.id, action=f'organizer_{decision}', target_type='organizer_application', target_id=application_id))
    db.commit()
    return {'message': 'Organizador aprobado.' if decision == 'approved' else 'Solicitud rechazada.',
            'status': decision}

@app.post('/api/admin/applications/{application_id}/approve')
def approve(application_id: int, body: ReviewBody, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return review(application_id,'approved',body,db,admin)

@app.post('/api/admin/applications/{application_id}/reject')
def reject(application_id: int, body: ReviewBody, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return review(application_id,'rejected',body,db,admin)

# --------------- Identidad por correo y recuperación ---------------
GENERIC_MAIL = 'Si el correo corresponde a una cuenta, recibirás instrucciones. Revisa tu bandeja.'

def _normalize_email(value: str) -> str:
    value = value.strip().casefold()
    if len(value) > 255 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise HTTPException(422, 'Escribe un correo electrónico válido.')
    return value

def _recent_tokens(db: Session, user_id: int, purpose: str):
    """Máximo 3 correos por hora para la misma cuenta y propósito."""
    threshold = now() - timedelta(hours=1)
    return len(db.scalars(select(AuthToken.id).where(AuthToken.user_id == user_id,
                  AuthToken.purpose == purpose, AuthToken.created_at > threshold)).all()) < 3

@app.post('/api/auth/resend-verification')
def resend_verification(body: EmailBody, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == _normalize_email(body.email)))
    if user and user.email_verified_at is None and _recent_tokens(db, user.id, 'email_verification'):
        token = make_token(db, user.id, 'email_verification', 24)
        try:
            send_mail(user.email, 'Verifica tu correo de BeatPass',
                      f'Confirma tu correo en 24 horas:\n{link("verify-email", token)}')
            db.commit()
        except RuntimeError:
            db.rollback()
    return {'message': GENERIC_MAIL}

@app.post('/api/auth/verify-email')
def verify_email(body: TokenBody, db: Session = Depends(get_db)):
    record = db.scalar(select(AuthToken).where(AuthToken.token_digest == digest(body.token),
                                               AuthToken.purpose == 'email_verification').with_for_update())
    if not is_valid(record):
        raise HTTPException(400, 'El enlace no es válido o ha expirado. Solicita uno nuevo.')
    user = db.get(User, record.user_id)
    if not user:
        raise HTTPException(400, 'El enlace ya no está disponible.')
    user.email_verified_at = now()
    record.used_at = now()
    # El resto de enlaces de verificación quedan inutilizados.
    for old in db.scalars(select(AuthToken).where(AuthToken.user_id == user.id,
                  AuthToken.purpose == 'email_verification', AuthToken.used_at.is_(None))).all():
        old.used_at = now()
    db.commit()
    return {'message': 'Correo verificado. Ya puedes iniciar sesión.'}

@app.post('/api/auth/forgot-password')
def forgot_password(body: EmailBody, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == _normalize_email(body.email)))
    if user and user.status == 'active' and user.email_verified_at is not None and _recent_tokens(db, user.id, 'password_reset'):
        token = make_token(db, user.id, 'password_reset', 1)
        try:
            send_mail(user.email, 'Recupera tu contraseña de BeatPass',
                      f'Para establecer una nueva contraseña, abre este enlace en la próxima hora:\n{link("reset-password", token)}\nSi no solicitaste el cambio, ignora el mensaje.')
            db.commit()
        except RuntimeError:
            db.rollback()
    return {'message': GENERIC_MAIL}

@app.post('/api/auth/reset-password')
def reset_password(body: PasswordResetBody, db: Session = Depends(get_db)):
    record = db.scalar(select(AuthToken).where(AuthToken.token_digest == digest(body.token),
                  AuthToken.purpose == 'password_reset').with_for_update())
    if not is_valid(record):
        raise HTTPException(400, 'El enlace ya expiró o fue utilizado. Solicita uno nuevo.')
    user = db.get(User, record.user_id)
    if not user:
        raise HTTPException(400, 'Enlace inválido.')
    user.password_hash = hash_password(body.password)
    user.token_version += 1  # Invalida todos los JWT emitidos con la contraseña antigua.
    for pending in db.scalars(select(AuthToken).where(AuthToken.user_id == user.id,
                  AuthToken.purpose == 'password_reset', AuthToken.used_at.is_(None))).all():
        pending.used_at = now()
    db.add(AuditLog(actor_id=user.id, action='password_reset', target_type='user', target_id=user.id))
    db.commit()
    return {'message': 'Contraseña actualizada. Inicia sesión con la nueva contraseña.'}

# -------------------- Invitaciones administrativas --------------------
@app.get('/api/admin/invitations')
def admin_invitations(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    records = db.scalars(select(AdminInvitation).order_by(AdminInvitation.created_at.desc()).limit(100)).all()
    return [{'id': i.id, 'email': i.email, 'status': ('accepted' if i.accepted_at else
            'revoked' if i.revoked_at else 'expired' if not is_valid_invitation(i) else 'pending'),
            'expires_at': i.expires_at.isoformat()} for i in records]

def is_valid_invitation(invitation):
    if not invitation or invitation.revoked_at or invitation.accepted_at:
        return False
    expiry = invitation.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry > now()

@app.post('/api/admin/invitations', status_code=201)
def create_admin_invitation(body: EmailBody, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    email = _normalize_email(body.email)
    existing = db.scalar(select(User).where(User.email == email))
    if existing and 'administracion' in roles(existing):
        raise HTTPException(409, 'Este correo ya tiene acceso administrativo.')
    pending = db.scalars(select(AdminInvitation).where(AdminInvitation.email == email,
               AdminInvitation.accepted_at.is_(None), AdminInvitation.revoked_at.is_(None))).all()
    for record in pending:
        record.revoked_at = now()
    from secrets import token_urlsafe
    token = token_urlsafe(40)
    invitation = AdminInvitation(email=email, token_digest=digest(token),
                                 issued_by=admin.id, expires_at=now() + timedelta(hours=48))
    db.add(invitation)
    try:
        db.flush()
        send_mail(email, 'Invitación administrativa de BeatPass',
                  f'Un administrador de BeatPass te invitó a su equipo.\n'
                  f'Para aceptar, crea primero una cuenta normal y verifica tu correo si aún no tienes cuenta.\n'
                  f'Abre en las próximas 48 horas: {link("accept-invitation", token)}\n'
                  f'Se solicitará tu contraseña para confirmar la aceptación. Si no esperabas esto, ignora el mensaje.')
        db.add(AuditLog(actor_id=admin.id, action='admin_invitation_sent',
                        target_type='admin_invitation', target_id=invitation.id))
        db.commit()
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(503, 'No se pudo enviar la invitación. Reintenta luego.') from exc
    return {'message': 'Invitación enviada al correo indicado; vence en 48 horas.'}

@app.post('/api/admin/invitations/{invitation_id}/revoke')
def revoke_admin_invitation(invitation_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    invitation = db.get(AdminInvitation, invitation_id)
    if not is_valid_invitation(invitation):
        raise HTTPException(409, 'La invitación no está activa.')
    invitation.revoked_at = now()
    db.add(AuditLog(actor_id=admin.id, action='admin_invitation_revoked',
                    target_type='admin_invitation', target_id=invitation.id))
    db.commit()
    return {'message': 'Invitación revocada.'}

@app.post('/api/auth/accept-admin-invitation')
def accept_admin_invitation(body: InvitationAcceptBody, db: Session = Depends(get_db)):
    invitation = db.scalar(select(AdminInvitation).where(
        AdminInvitation.token_digest == digest(body.token)).with_for_update())
    if not is_valid_invitation(invitation):
        raise HTTPException(400, 'La invitación venció o fue utilizada.')
    email = _normalize_email(body.email)
    user = db.scalar(select(User).where(User.email == email))
    if (email != invitation.email or not user or user.email_verified_at is None
            or user.status != 'active' or not verify_password(user.password_hash, body.password)):
        raise HTTPException(403, 'La cuenta debe existir, estar verificada y sus credenciales deben ser correctas.')
    if 'administracion' not in roles(user):
        db.add(UserRole(user_id=user.id, role_code='administracion'))
    invitation.accepted_at = now()
    db.add(AuditLog(actor_id=user.id, action='admin_invitation_accepted',
                    target_type='admin_invitation', target_id=invitation.id))
    db.commit()
    return {'message': 'Invitación aceptada. Puedes iniciar sesión como Administración.'}


# Las rutas de eventos usan la autenticación y autorización de este módulo.
from .events import router as events_router
app.include_router(events_router)

from .cart import router as cart_router
app.include_router(cart_router)

# Mi perfil: backend/profile.py reutiliza authenticated_user definido arriba.
from .profile import router as profile_router
app.include_router(profile_router)

# FLUJO: cart.js -> backend/orders.py -> reservas, pedidos y boletos demo.
from .orders import router as orders_router
app.include_router(orders_router)

# FLUJO: cart.js -> payments.py -> webhook firmado -> orders.py; solo sandbox.
from .payments import router as payments_router
app.include_router(payments_router)
