"""Pruebas de inventario y carrito, sin ventas ni pagos."""
# FLUJO: Prueba aislada -> backend/main.py y rutas relacionadas; no modifica BD de usuario.
import os
import tempfile
from pathlib import Path
from uuid import uuid4
from datetime import date, timedelta

# Ejecutable por separado en SQLite temporal.
_temp = tempfile.TemporaryDirectory(prefix='beatpass-2c-')
if 'backend.main' not in __import__('sys').modules:
    os.environ['APP_ENV'] = 'local'
    os.environ['DATABASE_URL'] = f"sqlite:///{Path(_temp.name) / 'cart.db'}"
    os.environ['SECRET_KEY'] = 'test-only-beatpass-2c-123456789123456789'

from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.main import app
from backend.database import SessionLocal
from backend.models import User, UserRole, OrganizerProfile, utc_now
from backend.security import hash_password, issue_token
from backend.inventory_models import TicketInventory
from backend.event_models import Event


def user(role=None):
    email = str(uuid4()) + '@example.test'
    with SessionLocal() as db:
        record = User(email=email, fullname='Cuenta de prueba', password_hash=hash_password('safe-test-123456'),
                      email_verified_at=utc_now())
        record.roles.append(UserRole(role_code='cliente'))
        if role:
            record.roles.append(UserRole(role_code=role))
        if role == 'organizador':
            record.organizer_profile = OrganizerProfile(display_name='Empresa prueba', phone='1234', city='Bogotá',
                                                        description='Para verificar compras', status='approved')
        db.add(record);db.commit()
        return {'Authorization': f'Bearer {issue_token(record.id, record.token_version)}'}


def payload(cap=5, seating='General por zonas', name='Festival de otoño'):
    return {'title':name, 'category':'Música', 'short':'Festival de rock con entrada por zonas.',
            'description':'Concierto de rock para todas las edades con artistas invitados.',
            'date':str(date.today()+timedelta(days=40)), 'time':'20:00', 'venue':'Auditorio principal',
            'city':'Bogotá', 'address':'Cra 3', 'timezone':'America/Bogota', 'seating':seating,
            'ticketTypes':[{'name':'General','price':80000,'capacity':cap, 'description':''},
                           {'name':'VIP','price':125000,'capacity':12,'description':'Cerca del escenario'}]}


def publish(client, organizer, admin, body=None):
    res = client.post('/api/organizers/events', headers=organizer, json=body or payload())
    assert res.status_code == 201, res.text
    event_id=res.json()['id']
    sent=client.post(f'/api/organizers/events/{event_id}/submit',headers=organizer)
    assert sent.status_code==200, sent.text
    pending=client.get('/api/admin/events/reviews',headers=admin).json()
    proposal=next(e for e in pending if e['id']==event_id)
    approved=client.post(f"/api/admin/events/reviews/{proposal['revision_id']}/approve",headers=admin,json={})
    assert approved.status_code==200, approved.text
    return event_id


def test_cart_lifecycle_isolation_and_validations():
    with TestClient(app) as client:
        organizer=user('organizador');admin=user('administracion');buyer=user();other=user()
        event_id=publish(client,organizer,admin)
        assert client.get('/api/cart').status_code==401
        assert client.get(f'/api/events/{event_id}/availability').json()['zones'][0]['available']==5
        assert client.post('/api/cart/items',headers=buyer,json={'event_id':event_id,'zone_index':0,'quantity':6}).status_code==409
        assert client.post('/api/cart/items',headers=buyer,json={'event_id':event_id,'zone_index':0,'quantity':0}).status_code==422
        assert client.post('/api/cart/items',headers=buyer,json={'event_id':event_id,'zone_index':15,'quantity':1}).status_code==422
        assert client.post('/api/cart/items',headers=buyer,json={'event_id':event_id,'zone_index':0,'quantity':1,'price':1}).status_code==422
        assert client.post('/api/cart/items',headers=buyer,json={'event_id':event_id,'zone_index':0,'quantity':1}).status_code==201
        added=client.post('/api/cart/items',headers=buyer,json={'event_id':event_id,'zone_index':0,'quantity':2})
        assert added.status_code==201,added.text
        cart=added.json();line=cart['items'][0]
        assert line['quantity']==3 and line['unit_price']==80000 and cart['subtotal']==240000
        assert cart['total_items']==3 and not cart['has_issues']
        assert client.get('/api/cart',headers=other).json()['items']==[]
        assert client.patch(f"/api/cart/items/{line['id']}",headers=other,json={'quantity':2}).status_code==404
        assert client.delete(f"/api/cart/items/{line['id']}",headers=other).status_code==404
        assert client.patch(f"/api/cart/items/{line['id']}",headers=buyer,json={'quantity':7}).status_code==409
        updated=client.patch(f"/api/cart/items/{line['id']}",headers=buyer,json={'quantity':4})
        assert updated.status_code==200 and updated.json()['subtotal']==320000
        assert client.get(f'/api/events/{event_id}/availability').json()['zones'][0]['available']==5 # carrito no reserva
        assert client.delete(f"/api/cart/items/{line['id']}",headers=buyer).json()['total_items']==0
        assert client.delete('/api/cart',headers=buyer).status_code==200


def test_pending_or_numbered_events_cannot_be_added():
    with TestClient(app) as client:
        organizer=user('organizador');admin=user('administracion');buyer=user()
        draft=client.post('/api/organizers/events',headers=organizer,json=payload()).json()['id']
        assert client.get(f'/api/events/{draft}/availability').status_code==404
        assert client.post('/api/cart/items',headers=buyer,json={'event_id':draft,'zone_index':0,'quantity':1}).status_code==404
        numbered=publish(client,organizer,admin,payload(seating='Asientos numerados'))
        availability=client.get(f'/api/events/{numbered}/availability').json()
        assert not availability['reservable']
        assert client.post('/api/cart/items',headers=buyer,json={'event_id':numbered,'zone_index':0,'quantity':1}).status_code==409


def test_updated_publication_marks_old_cart_as_outdated():
    with TestClient(app) as client:
        organizer=user('organizador');admin=user('administracion');buyer=user()
        event_id=publish(client,organizer,admin)
        assert client.post('/api/cart/items',headers=buyer,json={'event_id':event_id,'zone_index':0,'quantity':2}).status_code==201
        changes=payload(cap=7,name='Festival modificado')
        assert client.put(f'/api/organizers/events/{event_id}',headers=organizer,json=changes).status_code==200
        assert client.get('/api/cart',headers=buyer).json()['items'][0]['status']=='active'
        assert client.post(f'/api/organizers/events/{event_id}/submit',headers=organizer).status_code==200
        rev=next(x for x in client.get('/api/admin/events/reviews',headers=admin).json() if x['id']==event_id)
        assert client.post(f"/api/admin/events/reviews/{rev['revision_id']}/approve",headers=admin,json={}).status_code==200
        cart=client.get('/api/cart',headers=buyer).json()
        assert cart['items'][0]['status']=='outdated' and cart['subtotal']==0 and cart['has_issues']
        assert client.patch(f"/api/cart/items/{cart['items'][0]['id']}",headers=buyer,json={'quantity':1}).status_code==409
        new=client.post('/api/cart/items',headers=buyer,json={'event_id':event_id,'zone_index':0,'quantity':1})
        assert new.status_code==201 and len(new.json()['items'])==2
        with SessionLocal() as db:
            event=db.get(Event,event_id)
            assert len(db.scalars(select(TicketInventory).where(TicketInventory.event_id==event.id)).all())==4


def test_existing_2b_zone_without_capacity_defaults_to_zero_not_fake_stock():
    with TestClient(app) as client:
        organizer=user('organizador');admin=user('administracion');buyer=user()
        old=payload()
        for item in old['ticketTypes']:item.pop('capacity')
        event_id=publish(client,organizer,admin,old)
        result=client.get(f'/api/events/{event_id}/availability').json()
        assert all(z['available']==0 for z in result['zones'])
        assert client.post('/api/cart/items',headers=buyer,json={'event_id':event_id,'zone_index':0,'quantity':1}).status_code==409


def test_local_cors_preflight_and_legacy_inventory_migration():
    from sqlalchemy import delete
    from backend.main import init_schema
    with TestClient(app) as client:
        cors = client.options('/api/cart/items/1', headers={
            'Origin': 'http://127.0.0.1:8001',
            'Access-Control-Request-Method': 'PATCH',
            'Access-Control-Request-Headers': 'authorization,content-type'
        })
        assert cors.status_code == 200, cors.text
        assert cors.headers['access-control-allow-origin'] == 'http://127.0.0.1:8001'
        organizer=user('organizador');admin=user('administracion')
        event_id=publish(client,organizer,admin)
        # Simula una instalación 2B: publicación aprobada pero todavía sin filas 2C.
        with SessionLocal() as db:
            db.execute(delete(TicketInventory).where(TicketInventory.event_id == event_id))
            db.commit()
        init_schema()
        available=client.get(f'/api/events/{event_id}/availability').json()
        assert [z['available'] for z in available['zones']] == [5, 12]
