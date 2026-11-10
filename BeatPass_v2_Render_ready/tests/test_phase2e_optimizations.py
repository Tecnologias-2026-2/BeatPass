"""Comprobaciones específicas: búsqueda SQL paginada y límite de intentos."""
from datetime import date, timedelta, datetime, timezone
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_phase2d import account, details
from backend.main import app
from backend.database import SessionLocal
from backend.event_models import Event, EventRevision
from backend.models import LoginThrottle, User
from backend.login_limiter import _key


def test_search_filters_before_pagination_even_after_200_events():
    with TestClient(app) as client:
        organizer_id,_=account('organizador')
        original=details()
        with SessionLocal() as db:
            for i in range(212):
                event=Event(organizer_id=organizer_id)
                db.add(event); db.flush()
                data={**original,'title':('Archivo único perdido' if i==0 else f'Evento de pruebas {i:03d}'),
                      'category':'Música', 'date': str(date.today()+timedelta(days=65))}
                revision=EventRevision(event_id=event.id,version=1,status='approved',content=data)
                db.add(revision);db.flush()
                event.published_revision_id=revision.id
            db.commit()
        matched=client.get('/api/events',params={'q':'Archivo único','category':'Música','limit':10})
        assert matched.status_code==200,matched.text
        assert len(matched.json())==1 and matched.json()[0]['title']=='Archivo único perdido'
        first=client.get('/api/events',params={'limit':10,'offset':0}).json()
        second=client.get('/api/events',params={'limit':10,'offset':10}).json()
        assert len(first)==10 and len(second)==10
        assert not set(x['id'] for x in first) & set(x['id'] for x in second)


def test_login_limiter_blocks_repeated_wrong_passwords():
    with TestClient(app) as client:
        uid,_=account()
        with SessionLocal() as db:
            user=db.get(User,uid)
            email=user.email
        for _ in range(8):
            assert client.post('/api/auth/login',json={'email':email,'password':'wrong-password',
                    'profile':'cliente'}).status_code==401
        assert client.post('/api/auth/login',json={'email':email,'password':'wrong-password',
               'profile':'cliente'}).status_code==429
        with SessionLocal() as db:
            throttle=db.get(LoginThrottle,_key(email));assert throttle.attempts==8
            throttle.window_started=datetime.now(timezone.utc)-timedelta(minutes=16)
            db.commit()
        assert client.post('/api/auth/login',json={'email':email,'password':'strong-password-test',
               'profile':'cliente'}).status_code==200
