"""Mi perfil: consulta y edición de cuenta. El HTML llama a js/pages/profile.js,
ese JS utiliza js/core/api.js y este router valida todo antes de guardar en users.
"""
# FLUJO: profile.js -> api.js -> profile.py; JWT validado en main.authenticated_user().
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from .main import authenticated_user, user_view
from .models import User, AuditLog
from .schemas import ProfileNameBody, ProfilePasswordBody
from .security import verify_password, hash_password

router = APIRouter(prefix='/api/profile', tags=['Mi perfil'])

def view(user: User) -> dict:
    """Información privada, siempre obtenida del token verificado, no de un id enviado."""
    data = user_view(user)
    data['created_at'] = user.created_at.isoformat() if user.created_at else None
    if user.organizer_profile:
        organization = user.organizer_profile
        data['organization'] = {
            'name': organization.display_name,
            'city': organization.city,
            'status': organization.status,
        }
    else:
        data['organization'] = None
    return data

@router.get('')
def get_profile(user: User = Depends(authenticated_user)):
    # Viene de profile.js -> api.profile(); solo el titular puede ver sus datos.
    return view(user)

@router.patch('')
def update_profile(body: ProfileNameBody, db: Session = Depends(get_db),
                   user: User = Depends(authenticated_user)):
    # profile.js -> api.updateProfile() -> models.User -> SQLite/PostgreSQL.
    name = ' '.join(body.fullname.split())
    if len(name) < 2:
        raise HTTPException(422, 'Escribe un nombre válido.')
    user.fullname = name
    db.add(AuditLog(actor_id=user.id, action='profile_name_updated',
                    target_type='user', target_id=user.id))
    db.commit()
    db.refresh(user)
    return {'message': 'Nombre actualizado.', 'user': user_view(user)}

@router.post('/change-password')
def change_password(body: ProfilePasswordBody, db: Session = Depends(get_db),
                    user: User = Depends(authenticated_user)):
    # Nunca recibe un id de usuario: authenticated_user obtiene la cuenta del JWT.
    if not verify_password(user.password_hash, body.current_password):
        raise HTTPException(403, 'La contraseña actual es incorrecta.')
    if verify_password(user.password_hash, body.new_password):
        raise HTTPException(422, 'La contraseña nueva debe ser diferente de la actual.')
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1  # Invalida sesiones anteriores, incluida la actual.
    db.add(AuditLog(actor_id=user.id, action='profile_password_changed',
                    target_type='user', target_id=user.id))
    db.commit()
    return {'message': 'Contraseña actualizada. Inicia sesión nuevamente en tus dispositivos.'}
