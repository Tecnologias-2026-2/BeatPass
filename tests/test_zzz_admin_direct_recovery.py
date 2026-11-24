"""Comportamientos nuevos: publicación administrativa directa, rescate de rechazos y registro inmediato."""
from datetime import date, timedelta
import os
import sys
import tempfile
from pathlib import Path

_temp = tempfile.TemporaryDirectory(prefix='beatpass-admin-restore-')
if 'backend.main' not in sys.modules:
    os.environ['APP_ENV'] = 'local'
    os.environ['DATABASE_URL'] = f"sqlite:///{Path(_temp.name) / 'admin-tests.db'}"
    os.environ['SECRET_KEY'] = 'test-admin-controls-only-123456789-123456789'
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import User, UserRole, OrganizerProfile, utc_now, AuditLog
from backend.security import hash_password, issue_token
from sqlalchemy import select


def actor(email, role):
    with SessionLocal() as db:
        user=User(email=email, fullname=email, password_hash=hash_password('safe-test-password-123'),
                  email_verified_at=utc_now())
        user.roles.append(UserRole(role_code='cliente'))
        if role != 'cliente':
            user.roles.append(UserRole(role_code=role))
        if role == 'organizador':
            user.organizer_profile=OrganizerProfile(display_name='Organizador Test', phone='123', city='Bogotá',
                                                    description='Eventos de prueba', status='approved')
        db.add(user);db.commit()
        return {'Authorization': 'Bearer '+issue_token(user.id,user.token_version)}, user.id


def event_payload(title='Festival Administrado'):
    return {'title':title,'category':'Música','short':'Concierto para la comunidad',
            'description':'Música en vivo para toda la comunidad de BeatPass.',
            'date':str(date.today()+timedelta(days=130)), 'time':'20:00',
            'venue':'Teatro Central','city':'Bogotá','address':'Calle 5',
            'seating':'General por zonas','timezone':'America/Bogota',
            'ticketTypes':[{'name':'General','price':40000,'capacity':25,'description':'Zona'}]}


def test_admin_publish_own_event_without_self_approval_and_no_escalation():
    with TestClient(app) as c:
        admin,_=actor('admin-direct@beatpass.test','administracion')
        other_admin,_=actor('admin-other@beatpass.test','administracion')
        org,_=actor('org-direct@beatpass.test','organizador')
        own=c.post('/api/organizers/events',json=event_payload(),headers=admin)
        assert own.status_code==201,own.text
        ident=own.json()['id']
        assert c.get(f'/api/events/{ident}').status_code==404
        assert c.post(f'/api/organizers/events/{ident}/publish',headers=org).status_code==403
        assert c.post(f'/api/organizers/events/{ident}/publish',headers=other_admin).status_code==404
        published=c.post(f'/api/organizers/events/{ident}/publish',headers=admin)
        assert published.status_code==200,published.text
        assert c.get(f'/api/events/{ident}').json()['title']=='Festival Administrado'
        assert c.post(f'/api/organizers/events/{ident}/publish',headers=admin).status_code==409
        assert not any(row['id']==ident for row in c.get('/api/admin/events/reviews',headers=admin).json())
        # Versión posterior: la anterior sigue visible hasta que el propio admin vuelve a publicar.
        updated=c.put(f'/api/organizers/events/{ident}',headers=admin,json=event_payload('Nuevo Festival Administrado'))
        assert updated.status_code==200
        assert c.get(f'/api/events/{ident}').json()['title']=='Festival Administrado'
        assert c.post(f'/api/organizers/events/{ident}/publish',headers=admin).status_code==200
        assert c.get(f'/api/events/{ident}').json()['title']=='Nuevo Festival Administrado'
        org_event=c.post('/api/organizers/events',headers=org,json=event_payload('Organizador Normal')).json()['id']
        assert c.post(f'/api/organizers/events/{org_event}/publish',headers=org).status_code==403
        assert c.post(f'/api/organizers/events/{org_event}/submit',headers=org).status_code==200
        assert c.get(f'/api/events/{org_event}').status_code==404


def test_rejected_event_restored_to_pending_not_public_without_approval():
    with TestClient(app) as c:
        admin,_=actor('admin-restore@beatpass.test','administracion')
        org,_=actor('org-restore@beatpass.test','organizador')
        ordinary,_=actor('ordinary-restore@beatpass.test','cliente')
        eid=c.post('/api/organizers/events',headers=org,json=event_payload('Evento Recuperable')).json()['id']
        assert c.post(f'/api/organizers/events/{eid}/submit',headers=org).status_code==200
        rid=next(row['revision_id'] for row in c.get('/api/admin/events/reviews',headers=admin).json() if row['id']==eid)
        assert c.post(f'/api/admin/events/reviews/{rid}/reject',headers=admin,json={'reason':'Error accidental'}).status_code==200
        assert c.get('/api/admin/events/rejected',headers=ordinary).status_code==403
        rejected=c.get('/api/admin/events/rejected',headers=admin)
        assert rejected.status_code==200 and any(row['revision_id']==rid for row in rejected.json())
        assert c.post(f'/api/admin/events/reviews/{rid}/restore',headers=ordinary).status_code==403
        recovered=c.post(f'/api/admin/events/reviews/{rid}/restore',headers=admin)
        assert recovered.status_code==200,recovered.text
        assert c.get(f'/api/events/{eid}').status_code==404
        assert c.post(f'/api/admin/events/reviews/{rid}/restore',headers=admin).status_code==409
        assert any(row['revision_id']==rid for row in c.get('/api/admin/events/reviews',headers=admin).json())
        assert c.post(f'/api/admin/events/reviews/{rid}/approve',headers=admin,json={}).status_code==200
        assert c.get(f'/api/events/{eid}').status_code==200
        with SessionLocal() as db:
            assert db.scalar(select(AuditLog.id).where(AuditLog.action=='event_rejection_restored',
                AuditLog.target_id==rid)) is not None


def test_rejected_organizer_restored_without_granting_role():
    with TestClient(app) as c:
        admin,_=actor('admin-account-restore@beatpass.test','administracion')
        ordinary,_=actor('client-account-restore@beatpass.test','cliente')
        reg=c.post('/api/auth/register',json={
            'fullname':'Nueva Organizadora','email':'organizer-rejected@beatpass.test',
            'password':'safe-test-password-123','profile':'organizador',
            'organization':'Organización R','phone':'123456789','city':'Bogotá',
            'description':'Eventos de prueba'})
        assert reg.status_code==201 and reg.json()['access_token']
        assert c.get('/api/auth/me',headers={'Authorization':'Bearer '+reg.json()['access_token']}).status_code==200
        app_id=next(row['id'] for row in c.get('/api/admin/applications',headers=admin).json()
                    if row['email']=='organizer-rejected@beatpass.test')
        assert c.post(f'/api/admin/applications/{app_id}/reject',headers=admin,
                      json={'reason':'Por error'}).status_code==200
        rejected=c.get('/api/admin/applications/rejected',headers=admin).json()
        assert any(row['id']==app_id for row in rejected)
        assert c.post(f'/api/admin/applications/{app_id}/restore',headers=ordinary).status_code==403
        assert c.post(f'/api/admin/applications/{app_id}/restore',headers=admin).status_code==200
        assert c.post(f'/api/admin/applications/{app_id}/restore',headers=admin).status_code==409
        assert c.post('/api/auth/login',json={'email':'organizer-rejected@beatpass.test',
              'password':'safe-test-password-123','profile':'organizador'}).status_code==403
        assert c.post(f'/api/admin/applications/{app_id}/approve',headers=admin,json={}).status_code==200
        assert c.post('/api/auth/login',json={'email':'organizer-rejected@beatpass.test',
              'password':'safe-test-password-123','profile':'organizador'}).status_code==200


def test_immediate_registration_does_not_send_mandatory_verification(monkeypatch):
    import backend.main as main
    def refuse_email(*_args,**_kwargs):
        raise AssertionError('El registro no debe enviar correos')
    monkeypatch.setattr(main,'send_mail',refuse_email)
    with TestClient(app) as c:
        reg=c.post('/api/auth/register',json={'fullname':'Usuario Directo',
            'email':'immediate@beatpass.test','password':'safe-test-password-123','profile':'cliente'})
        assert reg.status_code==201 and reg.json()['access_token']
        assert reg.json()['user']['email_verified'] is False
        assert c.get('/api/auth/me',headers={'Authorization':'Bearer '+reg.json()['access_token']}).status_code==200
        assert c.post('/api/auth/login',json={'email':'immediate@beatpass.test',
               'password':'safe-test-password-123','profile':'cliente'}).status_code==200
