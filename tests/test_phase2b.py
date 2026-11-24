"""Fase 2B: aprobación y permisos verificables sin depender del servidor externo."""
# FLUJO: Prueba aislada -> backend/main.py y rutas relacionadas; no modifica BD de usuario.
import os
import tempfile
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

# Si se ejecuta este archivo solo, preparar SQLite aislada antes de importar la API.
_temp = tempfile.TemporaryDirectory(prefix='beatpass-2b-')
if 'backend.main' not in __import__('sys').modules:
    os.environ['APP_ENV'] = 'local'
    os.environ['DATABASE_URL'] = f"sqlite:///{Path(_temp.name) / 'events-test.db'}"
    os.environ['SECRET_KEY'] = 'test-only-beatpass-2b-123456789123456789'

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import User, UserRole, OrganizerProfile, utc_now
from backend.security import hash_password, issue_token
from backend.event_models import Event, EventRevision, EventCover
from PIL import Image


def make_user(email, role=None, approved=True):
    with SessionLocal() as db:
        user = User(email=email, fullname=email, password_hash=hash_password('only-test-password-123'), email_verified_at=utc_now())
        user.roles.append(UserRole(role_code='cliente'))
        if role:
            user.roles.append(UserRole(role_code=role))
        if role == 'organizador':
            user.organizer_profile = OrganizerProfile(display_name=email, phone='123', city='Bogotá', description='Conciertos', status='approved')
        db.add(user);db.commit()
        return {'Authorization':f'Bearer {issue_token(user.id,user.token_version)}'}


def data(title='Festival de Primavera', when=None):
    return {'title':title,'category':'Música','short':'Un concierto para toda la familia.',
        'description':'Una experiencia de música en vivo con artistas invitados y escenario.',
        'date':str(when or (date.today()+timedelta(days=50))), 'time':'19:30',
        'venue':'Teatro Centro', 'city':'Bogotá', 'address':'Calle 12',
        'seating':'General por zonas','ticketTypes':[{'name':'General','price':100,'description':'Zona principal'},
        {'name':'VIP','price':260,'description':'Zona preferente'}]}


def test_event_lifecycle_and_visibility():
    with TestClient(app) as client:
        organizer=make_user('org2b@example.test','organizador')
        admin=make_user('admin2b@example.test','administracion')
        unrelated=make_user('other2b@example.test','organizador')
        ordinary=make_user('client2b@example.test')
        assert client.post('/api/organizers/events',json=data(),headers=ordinary).status_code==403
        assert client.post('/api/organizers/events',json=data()).status_code==401
        event=client.post('/api/organizers/events',json=data(),headers=organizer)
        assert event.status_code==201,event.text
        event_id=event.json()['id']
        assert event.json()['minPrice']==100
        assert client.get('/api/events').json()==[]
        assert client.get(f'/api/events/{event_id}').status_code==404
        assert client.get('/api/admin/events/reviews',headers=ordinary).status_code==403
        assert client.get(f'/api/organizers/events/{event_id}',headers=unrelated).status_code==404
        assert client.put(f'/api/organizers/events/{event_id}',headers=unrelated,json=data()).status_code==404
        assert client.post(f'/api/organizers/events/{event_id}/submit',headers=unrelated).status_code==404
        assert client.post(f'/api/organizers/events/{event_id}/cover',headers=unrelated,content=b'whatever').status_code==404

        # Portada real subida al servidor y privada hasta la publicación.
        output=BytesIO()
        Image.new('RGB',(120,80),(25,80,120)).save(output,format='PNG')
        response=client.post(f'/api/organizers/events/{event_id}/cover',headers={**organizer,'Content-Type':'image/png'},content=output.getvalue())
        assert response.status_code==200,response.text
        assert client.get(f'/api/events/{event_id}/cover').status_code==404
        assert client.get(f'/api/organizers/events/{event_id}/cover',headers=unrelated).status_code==404
        private=client.get(f'/api/organizers/events/{event_id}/cover',headers=organizer)
        assert private.status_code==200 and private.headers['content-type']=='image/jpeg'

        invalid=client.put(f'/api/organizers/events/{event_id}',headers=organizer,json={**data(), 'ticketTypes': []})
        assert invalid.status_code==422
        assert client.put(f'/api/organizers/events/{event_id}',headers=organizer,json=data(when=date.today()-timedelta(days=5))).status_code==200
        assert client.post(f'/api/organizers/events/{event_id}/submit',headers=organizer).status_code==422
        assert client.put(f'/api/organizers/events/{event_id}',headers=organizer,json=data()).status_code==200
        sent=client.post(f'/api/organizers/events/{event_id}/submit',headers=organizer)
        assert sent.status_code==200
        assert client.post(f'/api/organizers/events/{event_id}/submit',headers=organizer).status_code==409
        assert client.put(f'/api/organizers/events/{event_id}',headers=organizer,json=data(title='Modificado ilegalmente')).status_code==409
        pending=client.get('/api/admin/events/reviews',headers=admin).json()
        assert len(pending)==1
        rev_id=pending[0]['revision_id']
        assert client.get(f'/api/admin/events/reviews/{rev_id}/cover',headers=ordinary).status_code==403
        assert client.get(f'/api/admin/events/reviews/{rev_id}/cover',headers=admin).headers['content-type']=='image/jpeg'
        assert client.post(f'/api/admin/events/reviews/{rev_id}/reject',headers=admin,json={'reason':''}).status_code==422
        assert client.post(f'/api/admin/events/reviews/{rev_id}/approve',headers=ordinary,json={}).status_code==403
        accepted=client.post(f'/api/admin/events/reviews/{rev_id}/approve',headers=admin,json={})
        assert accepted.status_code==200,accepted.text
        assert client.post(f'/api/admin/events/reviews/{rev_id}/approve',headers=admin,json={}).status_code==409
        view=client.get(f'/api/events/{event_id}').json()
        assert view['title']=='Festival de Primavera' and view['hasCover'] is True
        assert client.get(f'/api/events/{event_id}/cover').headers['content-type']=='image/jpeg'
        assert len(client.get('/api/events?q=primavera').json())==1
        assert client.get('/api/events?category=Teatro').json()==[]

        # La edición no sobrescribe la versión que el público ve.
        edit=client.put(f'/api/organizers/events/{event_id}',json=data('Festival Mejorado'),headers=organizer)
        assert edit.status_code==200 and edit.json()['version']==2
        assert client.get(f'/api/events/{event_id}').json()['title']=='Festival de Primavera'
        assert client.post(f'/api/organizers/events/{event_id}/submit',headers=organizer).status_code==200
        revision_two=client.get('/api/admin/events/reviews',headers=admin).json()[0]['revision_id']
        assert client.post(f'/api/admin/events/reviews/{revision_two}/reject',headers=admin,json={'reason':'Revisar descripción'}).status_code==200
        assert client.get(f'/api/events/{event_id}').json()['title']=='Festival de Primavera'
        assert client.get(f'/api/organizers/events/{event_id}',headers=organizer).json()['review_reason']=='Revisar descripción'
        corrected=client.put(f'/api/organizers/events/{event_id}',json=data('Festival Mejorado'),headers=organizer)
        assert corrected.status_code==200
        assert client.post(f'/api/organizers/events/{event_id}/submit',headers=organizer).status_code==200
        assert client.post(f'/api/admin/events/reviews/{revision_two}/approve',headers=admin,json={}).status_code==200
        assert client.get(f'/api/events/{event_id}').json()['title']=='Festival Mejorado'


def test_cannot_self_approve_even_as_admin():
    with TestClient(app) as client:
        same=make_user('creator-admin2b@example.test','administracion')
        created=client.post('/api/organizers/events',json=data('Evento de un administrador'),headers=same)
        assert created.status_code==201
        eid=created.json()['id']
        assert client.post(f'/api/organizers/events/{eid}/submit',headers=same).status_code==200
        rid=client.get('/api/admin/events/reviews',headers=same).json()[0]['revision_id']
        assert client.post(f'/api/admin/events/reviews/{rid}/approve',headers=same,json={}).status_code==403
        assert client.get(f'/api/events/{eid}').status_code==404
