"""Mi perfil: cambios persistentes y JWT inválidos tras actualizar contraseña.
FLUJO: profile.html -> profile.js -> api.js -> backend/profile.py -> SQLite temporal.
"""
import os
import tempfile
from pathlib import Path

# Aislar por completo las pruebas si se ejecuta este archivo individualmente.
_tmp = tempfile.TemporaryDirectory(prefix='beatpass-profile-')
os.environ.setdefault('APP_ENV', 'local')
os.environ.setdefault('SECRET_KEY', 'only-for-profile-tests-not-for-deployment-12345678')
os.environ.setdefault('DATABASE_URL', f'sqlite:///{Path(_tmp.name) / "profile.db"}')

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import User, UserRole, AuditLog, utc_now, OrganizerProfile
from backend.security import hash_password
from sqlalchemy import select

OLD = 'clave-anterior-robusta-2026'
NEW = 'clave-nueva-mas-segura-2026'


def create_user(email, with_org=False):
    with SessionLocal() as db:
        user = User(email=email, fullname='Laura Fernanda', password_hash=hash_password(OLD),
                    email_verified_at=utc_now())
        user.roles.append(UserRole(role_code='cliente'))
        if with_org:
            user.roles.append(UserRole(role_code='organizador'))
            user.organizer_profile = OrganizerProfile(display_name='Eventos Laura', phone='123',
                city='Bogotá', description='Conciertos', status='approved')
        db.add(user);db.commit()
        return user.id


def login(client, email):
    response = client.post('/api/auth/login', json={'email': email, 'password': OLD, 'profile': 'cliente'})
    assert response.status_code == 200, response.text
    return {'Authorization': 'Bearer ' + response.json()['access_token']}


def test_profile_requires_session_and_does_not_allow_role_edits():
    with TestClient(app) as client:
        assert client.get('/api/profile').status_code == 401
        assert client.patch('/api/profile', json={'fullname': 'Nombre nuevo'}).status_code == 401
        assert client.post('/api/profile/change-password', json={
            'current_password': OLD, 'new_password': NEW}).status_code == 401
        create_user('perfil-laura@example.test',with_org=True)
        headers = login(client, 'perfil-laura@example.test')
        profile=client.get('/api/profile',headers=headers)
        assert profile.status_code == 200,profile.text
        data=profile.json()
        assert data['fullname']=='Laura Fernanda' and data['email_verified']
        assert data['organization']['status']=='approved'
        assert 'organizador' in data['roles'] and 'password_hash' not in data
        assert client.patch('/api/profile',headers=headers,json={'fullname':'  '}).status_code==422
        assert client.patch('/api/profile',headers=headers,json={'fullname':'A'}).status_code==422
        assert client.patch('/api/profile',headers=headers,json={'fullname':'x'*121}).status_code==422
        assert client.patch('/api/profile',headers=headers,json={'fullname':'Admin Nuevo','roles':['administracion']}).status_code==422
        result=client.patch('/api/profile',headers=headers,json={'fullname':'  Laura   Nueva  '})
        assert result.status_code==200,result.text
        assert result.json()['user']['fullname']=='Laura Nueva'
        assert client.get('/api/auth/me',headers=headers).json()['fullname']=='Laura Nueva'
        assert client.get('/api/profile',headers=headers).json()['fullname']=='Laura Nueva'
        with SessionLocal() as db:
            user=db.scalar(select(User).where(User.email=='perfil-laura@example.test'))
            assert user.fullname=='Laura Nueva'
            assert {r.role_code for r in user.roles}=={'cliente','organizador'}
            assert db.scalar(select(AuditLog).where(AuditLog.actor_id==user.id,AuditLog.action=='profile_name_updated'))


def test_password_change_checks_current_password_and_invalidates_all_tokens():
    with TestClient(app) as client:
        create_user('perfil-clave@example.test')
        headers1 = login(client, 'perfil-clave@example.test')
        headers2 = login(client, 'perfil-clave@example.test')
        route='/api/profile/change-password'
        assert client.post(route,headers=headers1,json={'current_password':'incorrecta', 'new_password':NEW}).status_code==403
        assert client.post(route,headers=headers1,json={'current_password':OLD, 'new_password':'muy-corta'}).status_code==422
        assert client.post(route,headers=headers1,json={'current_password':OLD, 'new_password':OLD}).status_code==422
        assert client.get('/api/profile',headers=headers2).status_code==200
        changed=client.post(route,headers=headers1,json={'current_password':OLD, 'new_password':NEW})
        assert changed.status_code==200,changed.text
        assert client.get('/api/profile',headers=headers1).status_code==401
        assert client.get('/api/profile',headers=headers2).status_code==401
        assert client.post('/api/auth/login',json={'email':'perfil-clave@example.test', 'password':OLD,'profile':'cliente'}).status_code==401
        fresh=client.post('/api/auth/login',json={'email':'perfil-clave@example.test','password':NEW,'profile':'cliente'})
        assert fresh.status_code==200
        fresh_headers={'Authorization':'Bearer '+fresh.json()['access_token']}
        assert client.get('/api/profile',headers=fresh_headers).json()['fullname']=='Laura Fernanda'
