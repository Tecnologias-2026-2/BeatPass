"""Fase 2E: cobros de prueba con provider simulado, webhook firmado y conciliación de importes.

No hace llamadas a Mercado Pago ni cobra dinero. Usa la base temporal de test_phase2d.
"""
import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from test_phase2d import account, published, add
from backend.main import app
from backend import payments
from backend.database import SessionLocal
from backend.order_models import PurchaseOrder, PaymentAttempt, IssuedTicket
from backend.inventory_models import TicketInventory
from sqlalchemy import select


def signature(payment_id='12345', request_id='req-test', ts=None):
    ts=str(int(time.time()) if ts is None else ts)
    template=f'id:{payment_id.lower()};request-id:{request_id};ts:{ts};'
    digest=hmac.new(payments.MP_WEBHOOK_SECRET.encode(),template.encode(),hashlib.sha256).hexdigest()
    return {'x-signature':f'ts={ts},v1={digest}','x-request-id':request_id}


def setup_payment(monkeypatch, client, amount=35000):
    monkeypatch.setattr(payments,'PAYMENT_MODE','mercadopago_sandbox')
    monkeypatch.setattr(payments,'MP_WEBHOOK_SECRET','phase2e-test-webhook-secret')
    captured=[]
    def create_pref(order,ref,email):
        captured.append(ref)
        return {'id':'pref-demo','sandbox_init_point':'https://sandbox.mercadopago.com/pay?id=pref-demo'}
    monkeypatch.setattr(payments,'create_preference',create_pref)
    event,_,_=published(client,cap=2)
    _,owner=account()
    add(client,owner,event,1)
    hold=client.post('/api/checkout/hold',headers=owner).json()
    start=client.post(f"/api/orders/{hold['id']}/checkout-test",headers=owner)
    assert start.status_code==201,start.text
    assert start.json()['checkout_url'].startswith('https://sandbox.mercadopago.com/')
    assert len(captured)==1
    return hold,owner,event,captured


def test_gateway_disabled_by_default():
    with TestClient(app) as client:
        event,_,_=published(client)
        _,owner=account();add(client,owner,event,1)
        hold=client.post('/api/checkout/hold',headers=owner).json()
        denied=client.post(f"/api/orders/{hold['id']}/checkout-test",headers=owner)
        assert denied.status_code==503
        assert client.get('/api/checkout/config').json()['sandbox_enabled'] is False


def test_signed_webhook_confirms_only_verified_payment(monkeypatch):
    with TestClient(app) as client:
        hold,owner,event,refs=setup_payment(monkeypatch,client)
        order_id=hold['id']
        assert client.post(f'/api/orders/{order_id}/confirm-demo',headers=owner).status_code==409
        repeat=client.post(f'/api/orders/{order_id}/checkout-test',headers=owner)
        assert repeat.status_code==201 and len(refs)==1
        _,other=account()
        assert client.post(f'/api/orders/{order_id}/checkout-test',headers=other).status_code==404
        def provider(_id):
            return {'id':12345, 'live_mode':False, 'status':'approved',
                    'external_reference':refs[0], 'currency_id':'COP',
                    'transaction_amount':35000}
        monkeypatch.setattr(payments,'fetch_payment',provider)
        url='/api/payments/mercadopago/webhook?type=payment&data.id=12345'
        assert client.post(url).status_code==400
        bad=client.post(url,headers=signature(ts=1))
        assert bad.status_code==401
        valid=client.post(url,headers=signature())
        assert valid.status_code==200,valid.text
        assert valid.json()['status']=='sandbox_paid'
        assert client.post(url,headers=signature()).status_code==200  # idempotente
        assert client.get(f'/api/orders/{order_id}',headers=owner).json()['status']=='sandbox_paid'
        assert client.get(f'/api/orders/{order_id}',headers=owner).json()['payment']['status']=='approved_test'
        assert client.get('/api/tickets',headers=owner).json()[0]['demo'] is True
        with SessionLocal() as db:
            inv=db.scalar(select(TicketInventory).where(TicketInventory.event_id==event))
            tickets=db.scalars(select(IssuedTicket).where(IssuedTicket.owner_id==
                               db.get(PurchaseOrder,order_id).user_id)).all()
            assert inv.sold==1 and inv.held==0 and len(tickets)==1


def test_rejects_amount_live_mode_and_wrong_currency(monkeypatch):
    with TestClient(app) as client:
        hold,owner,event,refs=setup_payment(monkeypatch,client)
        base={'id':98765,'live_mode':False,'status':'approved',
              'external_reference':refs[0],'currency_id':'COP','transaction_amount':35000}
        url='/api/payments/mercadopago/webhook?type=payment&data.id=98765'
        for patch in [{'currency_id':'USD'},{'transaction_amount':1},{'live_mode':True}]:
            monkeypatch.setattr(payments,'fetch_payment',lambda _id,p=patch:{**base,**p})
            resp=client.post(url,headers=signature('98765'))
            assert resp.status_code==409,resp.text
        assert client.get(f"/api/orders/{hold['id']}",headers=owner).json()['status']=='reserved'
        assert client.get('/api/tickets',headers=owner).json()==[]


def test_pending_webhook_and_late_approval_never_issue_tickets(monkeypatch):
    with TestClient(app) as client:
        hold,owner,event,refs=setup_payment(monkeypatch,client)
        base={'id':22222,'live_mode':False,'status':'pending','external_reference':refs[0],
              'currency_id':'COP','transaction_amount':35000}
        monkeypatch.setattr(payments,'fetch_payment',lambda _id:base)
        url='/api/payments/mercadopago/webhook?type=payment&data.id=22222'
        assert client.post(url,headers=signature('22222')).json()['status']=='pending'
        with SessionLocal() as db:
            order=db.get(PurchaseOrder,hold['id'])
            order.expires_at=datetime.now(timezone.utc)-timedelta(minutes=1)
            db.commit()
        base['status']='approved'
        outcome=client.post(url,headers=signature('22222'))
        assert outcome.status_code==200,outcome.text
        assert outcome.json()['status']=='late_approved'
        assert client.get('/api/tickets',headers=owner).json()==[]
        assert client.get(f'/api/events/{event}/availability').json()['zones'][0]['available']==2
