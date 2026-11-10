"""Fase 2D: reservas atómicas, vencimiento, pedidos y boletos privados.
FLUJO: tests -> orders.py -> order_models.py; los datos de prueba viven en SQLite temporal.
"""
import os
import sys
import tempfile
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select

_work = tempfile.TemporaryDirectory(prefix='beatpass-2d-tests-')
if 'backend.main' not in sys.modules:
    os.environ['APP_ENV'] = 'local'
    os.environ['DATABASE_URL'] = f'sqlite:///{Path(_work.name) / "test.db"}'
    os.environ['SECRET_KEY'] = 'testing-key-for-phase2d-1234567890testing'

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import User, UserRole, OrganizerProfile, utc_now
from backend.security import hash_password, issue_token
from backend.event_models import Event
from backend.inventory_models import TicketInventory
from backend.order_models import PurchaseOrder, IssuedTicket


def account(role=None):
    with SessionLocal() as db:
        user = User(email=f'{uuid4()}@example.test', fullname='Persona Prueba',
                    password_hash=hash_password('strong-password-test'), email_verified_at=utc_now())
        user.roles.append(UserRole(role_code='cliente'))
        if role:
            user.roles.append(UserRole(role_code=role))
        if role == 'organizador':
            user.organizer_profile = OrganizerProfile(display_name='Evento Test', phone='3210000',
                city='Bogotá', description='Para probar las reservas', status='approved')
        db.add(user);db.commit()
        return user.id, {'Authorization': f'Bearer {issue_token(user.id,user.token_version)}'}


def details(cap=2):
    return {'title':'Evento para compras de prueba','category':'Música',
       'short':'Una muestra del sistema de pedidos y boletos.',
       'description':'Evento con inventario limitado para verificar transacciones seguras.',
       'date':str(date.today()+timedelta(days=60)), 'time':'18:00', 'venue':'Teatro Demo',
       'city':'Bogotá', 'address':'Calle 123', 'timezone':'America/Bogota',
       'seating':'General por zonas',
       'ticketTypes':[{'name':'General','price':35000,'capacity':cap,'description':''}]}


def published(client, cap=2):
    _,org=account('organizador');_,admin=account('administracion')
    created=client.post('/api/organizers/events',headers=org,json=details(cap))
    assert created.status_code==201,created.text
    event_id=created.json()['id']
    assert client.post(f'/api/organizers/events/{event_id}/submit',headers=org).status_code==200
    review=next(x for x in client.get('/api/admin/events/reviews',headers=admin).json() if x['id']==event_id)
    approved=client.post(f"/api/admin/events/reviews/{review['revision_id']}/approve",headers=admin,json={})
    assert approved.status_code==200,approved.text
    return event_id,org,admin


def add(client,headers,eid,qty):
    response=client.post('/api/cart/items',headers=headers,json={'event_id':eid,'zone_index':0,'quantity':qty})
    assert response.status_code==201,response.text


def test_hold_reduces_availability_and_cancel_restores_it():
    with TestClient(app) as client:
        event,_,_=published(client,cap=3)
        _,buyer=account();_,other=account()
        add(client,buyer,event,2)
        hold=client.post('/api/checkout/hold',headers=buyer)
        assert hold.status_code==201,hold.text
        order=hold.json()
        assert order['status']=='reserved' and order['subtotal']==70000
        assert client.get(f'/api/events/{event}/availability').json()['zones'][0]['available']==1
        assert client.post('/api/checkout/hold',headers=buyer).status_code==409
        assert client.get(f"/api/orders/{order['id']}",headers=other).status_code==404
        assert client.post(f"/api/orders/{order['id']}/cancel",headers=other).status_code==404
        assert client.post(f"/api/orders/{order['id']}/cancel",headers=buyer).json()['status']=='cancelled'
        assert client.get(f'/api/events/{event}/availability').json()['zones'][0]['available']==3
        assert client.post(f"/api/orders/{order['id']}/confirm-demo",headers=buyer).status_code==409


def test_no_overselling_when_two_buyers_try_last_cupos():
    with TestClient(app) as client:
        event,_,_=published(client,cap=2)
        _,buyer1=account();_,buyer2=account()
        add(client,buyer1,event,2)
        add(client,buyer2,event,2)
        assert client.post('/api/checkout/hold',headers=buyer1).status_code==201
        denied=client.post('/api/checkout/hold',headers=buyer2)
        assert denied.status_code==409,denied.text
        assert client.get(f'/api/events/{event}/availability').json()['zones'][0]['available']==0


def test_confirm_is_idempotent_creates_one_ticket_per_entry_and_private_qr():
    with TestClient(app) as client:
        event,org,admin=published(client,cap=3)
        uid,buyer=account();_,other=account()
        add(client,buyer,event,2)
        created=client.post('/api/checkout/hold',headers=buyer).json()
        order_id=created['id']
        confirmed=client.post(f'/api/orders/{order_id}/confirm-demo',headers=buyer)
        assert confirmed.status_code==200,confirmed.text
        assert confirmed.json()['status']=='demo_confirmed'
        assert client.post(f'/api/orders/{order_id}/confirm-demo',headers=buyer).status_code==200
        assert client.get('/api/cart',headers=buyer).json()['total_items']==0
        tickets=client.get('/api/tickets',headers=buyer)
        assert tickets.status_code==200
        assert len([x for x in tickets.json() if x['order_id']==order_id])==2
        ticket=tickets.json()[0]
        assert ticket['demo'] is True and ticket['status']=='demo'
        assert client.get('/api/tickets',headers=other).json()==[]
        assert client.get(f"/api/tickets/{ticket['id']}/qr",headers=other).status_code==404
        qr=client.get(f"/api/tickets/{ticket['id']}/qr",headers=buyer)
        assert qr.status_code==200 and qr.headers['content-type']=='image/png'
        assert qr.content.startswith(b'\x89PNG') and 'no-store' in qr.headers['cache-control']
        availability=client.get(f'/api/events/{event}/availability').json()['zones'][0]
        assert (availability['sold'],availability['available'])==(2,1)
        with SessionLocal() as db:
            order=db.get(PurchaseOrder,order_id)
            inv=db.scalar(select(TicketInventory).where(TicketInventory.event_id==event))
            assert order.status=='demo_confirmed' and inv.held==0 and inv.sold==2
            assert db.scalar(select(IssuedTicket).where(IssuedTicket.owner_id==uid)) is not None
        # Una nueva revisión no puede reiniciar inventario que ya fue confirmado.
        change=details(cap=100);change['title']='Evento con cambio bloqueado'
        assert client.put(f'/api/organizers/events/{event}',headers=org,json=change).status_code==200
        assert client.post(f'/api/organizers/events/{event}/submit',headers=org).status_code==200
        revision=next(x for x in client.get('/api/admin/events/reviews',headers=admin).json() if x['id']==event)
        assert client.post(f"/api/admin/events/reviews/{revision['revision_id']}/approve",headers=admin,json={}).status_code==409


def test_expired_order_releases_hold_and_cannot_be_confirmed():
    with TestClient(app) as client:
        event,_,_=published(client,cap=1)
        _,buyer=account()
        add(client,buyer,event,1)
        order=client.post('/api/checkout/hold',headers=buyer).json()
        with SessionLocal() as db:
            target=db.get(PurchaseOrder,order['id'])
            target.expires_at=datetime.now(timezone.utc)-timedelta(minutes=2)
            db.commit()
        availability=client.get(f'/api/events/{event}/availability').json()['zones'][0]
        assert availability['available']==1
        assert client.get(f"/api/orders/{order['id']}",headers=buyer).json()['status']=='expired'
        assert client.post(f"/api/orders/{order['id']}/confirm-demo",headers=buyer).status_code==409
        assert client.get('/api/tickets',headers=buyer).json()==[]
        assert client.post('/api/checkout/hold',headers=buyer).status_code==201


def test_orders_require_auth_and_reject_price_manipulation():
    with TestClient(app) as client:
        assert client.get('/api/orders').status_code==401
        assert client.get('/api/tickets').status_code==401
        assert client.post('/api/checkout/hold').status_code==401
        event,_,_=published(client,cap=2)
        _,buyer=account()
        add(client,buyer,event,1)
        assert client.post('/api/checkout/hold',headers=buyer,json={'total':1}).status_code==201
        assert client.get('/api/orders',headers=buyer).json()[-1]['subtotal']==35000


def test_cors_preflight_for_demo_confirmation():
    with TestClient(app) as client:
        response=client.options('/api/orders/1/confirm-demo',headers={
            'Origin':'http://127.0.0.1:8001','Access-Control-Request-Method':'POST',
            'Access-Control-Request-Headers':'authorization,content-type'})
        assert response.status_code==200 and response.headers['access-control-allow-origin']=='http://127.0.0.1:8001'
