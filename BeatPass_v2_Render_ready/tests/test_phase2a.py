"""Pruebas aisladas: no alteran ninguna base de datos del usuario."""
# FLUJO: Prueba aislada -> backend/main.py y rutas relacionadas; no modifica BD de usuario.
import os
import tempfile
from pathlib import Path

_temp = tempfile.TemporaryDirectory(prefix='beatpass-test-')
os.environ['APP_ENV'] = 'local'
os.environ['SECRET_KEY'] = 'only-for-isolated-tests-not-for-application-deployment-123456'
os.environ['DATABASE_URL'] = f"sqlite:///{Path(_temp.name) / 'test.db'}"

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import User, UserRole, utc_now
from sqlalchemy import select
from backend.security import hash_password
import re
from backend.config import ROOT as BACKEND_ROOT

def latest_mail_token(recipient, page):
    mailbox = (BACKEND_ROOT / 'instance' / 'dev-mailbox.txt').read_text(encoding='utf-8')
    section = [chunk for chunk in mailbox.split('--- ') if f'Para: {recipient.casefold()}' in chunk][-1]
    return re.search(rf'{page}\.html\?token=([A-Za-z0-9_\-]+)', section).group(1)



def test_registration_roles_approval_and_no_privilege_escalation():
    with TestClient(app) as client:
        # No existe un campo de registro que permita convertirse en administrador.
        bad = client.post('/api/auth/register', json={
            'fullname': 'Intento Admin', 'email': 'bad@example.test',
            'password': 'strong-password-123', 'profile': 'administracion'
        })
        assert bad.status_code == 422
        reg = client.post('/api/auth/register', json={
            'fullname': 'Ana Organizadora', 'email': 'Ana@Example.test',
            'password': 'password-for-demo-2026', 'profile': 'organizador',
            'organization': 'Eventos Ana', 'phone': '+573001111111',
            'city': 'Bogotá', 'description': 'Conciertos de música'
        })
        assert reg.status_code == 201, reg.text
        assert reg.json()['user']['roles'] == ['cliente']
        assert reg.json()['user']['organizer_status'] == 'pending'
        token = latest_mail_token('ana@example.test', 'verify-email')
        assert client.post('/api/auth/verify-email', json={'token':token}).status_code == 200
        denied = client.post('/api/auth/login', json={'email':'Ana@example.test',
                        'password':'password-for-demo-2026', 'profile':'organizador'})
        assert denied.status_code == 403
        ordinary = client.post('/api/auth/login',json={'email':'Ana@example.test',
                        'password':'password-for-demo-2026', 'profile':'cliente'})
        assert ordinary.status_code == 200
        client_headers = {'Authorization':f"Bearer {ordinary.json()['access_token']}"}
        assert client.get('/api/admin/applications',headers=client_headers).status_code == 403
        assert client.get('/api/auth/me',headers={'Authorization':'Bearer fake'}).status_code == 401

        # Bootstrap administrador simulado por el método interno, nunca por registro público.
        with SessionLocal() as db:
            admin = User(email='admin@example.test', fullname='Admin de pruebas',
                         password_hash=hash_password('admin-test-password-123'), email_verified_at=utc_now())
            admin.roles.append(UserRole(role_code='cliente'))
            admin.roles.append(UserRole(role_code='administracion'))
            db.add(admin); db.commit()
        admin_login = client.post('/api/auth/login', json={
            'email':'admin@example.test','password':'admin-test-password-123','profile':'administracion'
        })
        assert admin_login.status_code == 200
        admin_headers = {'Authorization':f"Bearer {admin_login.json()['access_token']}"}
        applications = client.get('/api/admin/applications', headers=admin_headers)
        assert applications.status_code == 200 and len(applications.json()) == 1
        request_id = applications.json()[0]['id']
        approval = client.post(f'/api/admin/applications/{request_id}/approve',
                               headers=admin_headers, json={'reason':'Datos verificados'})
        assert approval.status_code == 200
        assert client.post(f'/api/admin/applications/{request_id}/approve',
                           headers=admin_headers,json={}).status_code == 409
        approved = client.post('/api/auth/login', json={'email':'ana@example.test',
                           'password':'password-for-demo-2026','profile':'organizador'})
        assert approved.status_code == 200
        assert 'organizador' in approved.json()['user']['roles']
        assert 'administracion' not in approved.json()['user']['roles']


def test_password_duplicate_and_rejection():
    with TestClient(app) as client:
        original = {'fullname':'Ana Segunda', 'email':'repeat@example.test',
                    'password':'strong-passphrase-123','profile':'cliente'}
        assert client.post('/api/auth/register',json=original).status_code == 201
        duplicate = client.post('/api/auth/register',json=original)
        assert duplicate.status_code == 409
        weak = client.post('/api/auth/register',json={'fullname':'Ana Segunda',
                     'email':'new@example.test','password':'short','profile':'cliente'})
        assert weak.status_code == 422
        assert client.get('/api/health').json()['status'] == 'ok'


def test_cors_file_origin_local_only():
    with TestClient(app) as client:
        r = client.options('/api/auth/login',headers={
            'Origin':'null','Access-Control-Request-Method':'POST',
            'Access-Control-Request-Headers':'content-type'})
        assert r.status_code == 200
        assert r.headers.get('access-control-allow-origin') == 'null'


def test_verification_recovery_token_replay_and_jwt_revocation():
    from datetime import timedelta
    from backend.models import AuthToken
    with TestClient(app) as client:
        email = 'recovery@example.test'
        reg = client.post('/api/auth/register', json={'fullname':'Usuario Recovery', 'email':email,
                             'password':'old-password-12345', 'profile':'cliente'})
        assert reg.status_code == 201
        assert reg.json()['user']['email_verified'] is False
        assert client.post('/api/auth/login', json={'email':email,'password':'old-password-12345','profile':'cliente'}).status_code == 403
        token = latest_mail_token(email, 'verify-email')
        assert client.post('/api/auth/verify-email',json={'token':token}).status_code == 200
        assert client.post('/api/auth/verify-email',json={'token':token}).status_code == 400
        login = client.post('/api/auth/login',json={'email':email,'password':'old-password-12345','profile':'cliente'})
        assert login.status_code == 200
        previous_auth = {'Authorization': 'Bearer '+login.json()['access_token']}
        assert client.get('/api/auth/me',headers=previous_auth).status_code == 200
        unknown = client.post('/api/auth/forgot-password',json={'email':'not-on-file@example.test'})
        request = client.post('/api/auth/forgot-password',json={'email':email})
        assert unknown.json() == request.json()
        reset_token = latest_mail_token(email,'reset-password')
        bad = client.post('/api/auth/reset-password', json={'token':reset_token,'password':'short'})
        assert bad.status_code == 422
        good = client.post('/api/auth/reset-password',json={'token':reset_token,'password':'new-password-67890'})
        assert good.status_code == 200
        assert client.post('/api/auth/reset-password',json={'token':reset_token,'password':'reuse-password-54321'}).status_code == 400
        assert client.get('/api/auth/me',headers=previous_auth).status_code == 401
        assert client.post('/api/auth/login',json={'email':email,'password':'old-password-12345','profile':'cliente'}).status_code == 401
        assert client.post('/api/auth/login',json={'email':email,'password':'new-password-67890','profile':'cliente'}).status_code == 200
        # La verificación no puede modificarse mediante el cuerpo del registro.
        other = client.post('/api/auth/register',json={'fullname':'Sin verificar','email':'notverified@example.test',
               'password':'strong-pass-2026','profile':'cliente','email_verified':True})
        assert other.status_code == 201
        assert other.json()['user']['email_verified'] is False
        with SessionLocal() as db:
            record = db.scalar(select(AuthToken).where(AuthToken.purpose=='email_verification',
                 AuthToken.token_digest==__import__('backend.token_service',fromlist=['digest']).digest(latest_mail_token('notverified@example.test','verify-email'))))
            record.expires_at = utc_now() - timedelta(hours=1)
            db.commit()
        expired = client.post('/api/auth/verify-email', json={'token':latest_mail_token('notverified@example.test','verify-email')})
        assert expired.status_code == 400


def test_admin_email_invitations_must_be_verified_and_password_confirmed():
    from sqlalchemy import select
    from backend.models import AdminInvitation
    with TestClient(app) as client:
        admin = User(email='boss@example.test',fullname='Admin Invitaciones',
                     password_hash=hash_password('admin-invite-pass-123'),email_verified_at=utc_now())
        admin.roles.extend([UserRole(role_code='cliente'),UserRole(role_code='administracion')])
        with SessionLocal() as db:
            db.add(admin);db.commit()
        login_admin = client.post('/api/auth/login',json={'email':'boss@example.test',
                     'password':'admin-invite-pass-123','profile':'administracion'})
        assert login_admin.status_code == 200
        headers={'Authorization':'Bearer '+login_admin.json()['access_token']}
        email='newboss@example.test'
        assert client.post('/api/admin/invitations',json={'email':email}).status_code == 401
        sent=client.post('/api/admin/invitations',headers=headers,json={'email':email})
        assert sent.status_code == 201, sent.text
        invitation_token=latest_mail_token(email,'accept-invitation')
        # Aún no existe una cuenta; conocer el token no es suficiente.
        assert client.post('/api/auth/accept-admin-invitation',json={
            'email':email,'token':invitation_token,'password':'pass-pass-password-123'}).status_code == 403
        reg=client.post('/api/auth/register',json={'fullname':'Nuevo Admin','email':email,
                      'password':'pass-pass-password-123','profile':'cliente'})
        assert reg.status_code == 201
        assert client.post('/api/auth/accept-admin-invitation',json={
            'email':email,'token':invitation_token,'password':'pass-pass-password-123'}).status_code == 403
        verify=latest_mail_token(email,'verify-email')
        assert client.post('/api/auth/verify-email',json={'token':verify}).status_code == 200
        assert client.post('/api/auth/accept-admin-invitation',json={
            'email':email,'token':invitation_token,'password':'wrong-password'}).status_code == 403
        first_list = client.get('/api/admin/invitations',headers=headers).json()
        assert any(item['email']==email and item['status']=='pending' for item in first_list)
        # Revocar invalida inmediatamente el enlace anterior.
        invitation_id=next(item['id'] for item in first_list if item['email']==email)
        assert client.post(f'/api/admin/invitations/{invitation_id}/revoke',headers=headers).status_code == 200
        assert client.post('/api/auth/accept-admin-invitation',json={
            'email':email,'token':invitation_token,'password':'pass-pass-password-123'}).status_code == 400
        # Segunda invitación y aceptación válida.
        assert client.post('/api/admin/invitations',headers=headers,json={'email':email}).status_code == 201
        second_token=latest_mail_token(email,'accept-invitation')
        assert second_token != invitation_token
        accept=client.post('/api/auth/accept-admin-invitation',json={
            'email':email,'token':second_token,'password':'pass-pass-password-123'})
        assert accept.status_code == 200,accept.text
        assert client.post('/api/auth/accept-admin-invitation',json={
            'email':email,'token':second_token,'password':'pass-pass-password-123'}).status_code == 400
        login = client.post('/api/auth/login',json={'email':email,
                  'password':'pass-pass-password-123','profile':'administracion'})
        assert login.status_code == 200
        assert 'administracion' in login.json()['user']['roles']


def test_upgrade_from_2a_sqlite_preserves_users_and_marks_legacy_verified():
    import sqlite3
    import subprocess
    import sys
    with tempfile.TemporaryDirectory(prefix='beatpass-upgrade-') as folder:
        db_path = Path(folder) / 'legacy.db'
        conn = sqlite3.connect(db_path)
        conn.execute('''CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255) UNIQUE,
                     fullname VARCHAR(120), password_hash VARCHAR(255), status VARCHAR(20), created_at DATETIME)''')
        conn.execute('INSERT INTO users VALUES (1,?,?,?,?,?)',
                     ('old-account@example.test','Cuenta anterior','existing-hash','active','2026-01-01 10:00:00'))
        conn.commit(); conn.close()
        env = os.environ.copy()
        env['DATABASE_URL'] = f'sqlite:///{db_path}'
        env['APP_ENV'] = 'local'
        env['SECRET_KEY'] = 'only-for-isolated-migration-test-not-for-deploy'
        env['MAIL_MODE'] = 'development'
        proc = subprocess.run([sys.executable,'-c',
                    'from backend.main import init_schema; init_schema(); print("schema migrated")'],
                    cwd=Path(__file__).resolve().parents[1],env=env,
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30)
        assert proc.returncode == 0, proc.stderr
        conn = sqlite3.connect(db_path)
        row = conn.execute('SELECT email, email_verified_at, token_version FROM users WHERE id=1').fetchone()
        assert row[0] == 'old-account@example.test' and row[1] and row[2] == 0
        assert conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='auth_tokens'").fetchone()
        conn.close()


def test_mail_provider_uses_https_without_exposing_key(monkeypatch):
    import json
    from backend import email_service
    sent = {}
    class FakeResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def fake_urlopen(request,timeout):
        sent['url'] = request.full_url
        sent['headers'] = request.headers
        sent['data'] = json.loads(request.data.decode('utf-8'))
        return FakeResponse()
    monkeypatch.setattr(email_service,'MAIL_MODE','resend')
    monkeypatch.setattr(email_service,'MAIL_FROM','BeatPass <test@beatpass.test>')
    monkeypatch.setattr(email_service,'RESEND_API_KEY','test-only-example')
    monkeypatch.setattr(email_service,'urlopen',fake_urlopen)
    email_service.send_mail('user@example.test','Prueba de entrega','Mensaje de prueba')
    assert sent['url'] == 'https://api.resend.com/emails'
    assert sent['data']['text'] == 'Mensaje de prueba'
    assert sent['data']['to'] == ['user@example.test']
    assert sent['headers']['Authorization'] == 'Bearer test-only-example'


def test_cli_admin_creation_with_invisible_entry(monkeypatch):
    from backend import cli
    import builtins
    class FakeStdin:
        def isatty(self): return True
    monkeypatch.setattr(cli.sys,'stdin',FakeStdin())
    monkeypatch.setattr(builtins,'input',lambda prompt: 'Administrador CMD')
    calls=[]
    def getpass_mock(prompt):
        calls.append(prompt)
        return 'cmd-super-secret-123456'
    monkeypatch.setattr(cli.getpass,'getpass',getpass_mock)
    cli.create_admin('cmd@example.test')
    assert len(calls) == 2
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email=='cmd@example.test'))
        assert user.email_verified_at is not None
        assert 'administracion' in [r.role_code for r in user.roles]
        assert user.password_hash != 'cmd-super-secret-123456'


def test_rejects_malformed_addresses_before_sending_mail():
    """Los endpoints públicos no aceptan direcciones con @ repetidos ni espacios."""
    with TestClient(app) as client:
        for malformed in ('user@@example.test', 'name @example.test', 'user@example.test@other.test'):
            registration = client.post('/api/auth/register', json={
                'fullname': 'Prueba Correo', 'email': malformed,
                'password': 'strong-password-123', 'profile': 'cliente'
            })
            assert registration.status_code == 422
            assert client.post('/api/auth/forgot-password', json={'email': malformed}).status_code == 422
