"""Fase 2E: integración OPCIONAL con Mercado Pago (credenciales de prueba).

FLUJO: cart.js -> api.startSandboxPayment() -> payments.py -> Mercado Pago HTTPS.
FLUJO: Webhook firmado -> consulta GET al proveedor -> orders._finalize_reserved() -> SQLite/PostgreSQL.
NUNCA procesa tarjetas ni emite boletos válidos para acceso físico.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import secrets
import time
from urllib.parse import urlparse
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from .config import (PAYMENT_MODE, MP_ACCESS_TOKEN, MP_WEBHOOK_SECRET,
                     PUBLIC_FRONTEND_URL, PUBLIC_API_URL)
from .database import get_db
from .main import authenticated_user
from .models import User, AuditLog
from .order_models import PaymentAttempt, PurchaseOrder
from .orders import expire_orders, _owned_order, _finalize_reserved, utc_now

router = APIRouter(prefix='/api', tags=['Pagos de prueba (2E)'])
MP_API = 'https://api.mercadopago.com'


def _aware_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def sandbox_enabled() -> bool:
    return PAYMENT_MODE == 'mercadopago_sandbox'


def _require_sandbox():
    if not sandbox_enabled():
        raise HTTPException(503, 'El pago de prueba no está habilitado.')


def _provider_request(method: str, path: str, payload: dict | None = None) -> dict:
    """Solo se comunica con dominio fijo; jamás recibe un URL externo de un usuario."""
    try:
        with httpx.Client(timeout=12.0) as client:
            response = client.request(method, MP_API + path,
                headers={'Authorization': f'Bearer {MP_ACCESS_TOKEN}',
                         'Content-Type': 'application/json'}, json=payload)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, 'Mercado Pago no respondió correctamente. Reintenta más tarde.') from exc


def create_preference(order: PurchaseOrder, reference: str, email: str) -> dict:
    """Servidor calcula el monto desde la reserva, nunca desde datos enviados por JS."""
    items = [{'title': line.snapshot['event_title'][:80] + ' - ' + line.snapshot['zone_name'][:35],
              'quantity': line.quantity, 'unit_price': int(line.unit_price), 'currency_id': 'COP'}
             for line in order.items]
    payload = {
        'items': items,
        'payer': {'email': email},
        'external_reference': reference,
        'notification_url': PUBLIC_API_URL + '/api/payments/mercadopago/webhook',
        'back_urls': {state: PUBLIC_FRONTEND_URL + f'/pages/payment-result.html?order_id={order.id}&return={state}'
                      for state in ('success', 'pending', 'failure')},
        'auto_return': 'approved',
        'expires': True,
        'expiration_date_from': utc_now().isoformat(),
        'expiration_date_to': _aware_utc(order.expires_at).isoformat(),
    }
    return _provider_request('POST', '/checkout/preferences', payload)


def fetch_payment(payment_id: str) -> dict:
    if not payment_id.isdecimal() or len(payment_id) > 32:
        raise HTTPException(422, 'Identificador del pago inválido.')
    return _provider_request('GET', '/v1/payments/' + payment_id)


def _safe_checkout_url(value: str) -> bool:
    parsed = urlparse(value)
    return (parsed.scheme == 'https' and parsed.username is None and parsed.password is None
            and parsed.hostname in ('sandbox.mercadopago.com', 'sandbox.mercadopago.com.co'))


def _discard_attempt(db: Session, attempt_id: int | None) -> None:
    """Borra un intento que nunca llegó a tener dirección de pago.

    Solo se usa cuando el proveedor no creó una preferencia utilizable; si ya existe
    una preferencia, el intento se conserva para que el webhook pueda conciliarla.
    """
    attempt = db.get(PaymentAttempt, attempt_id)
    if attempt and not attempt.checkout_url and attempt.payment_id is None:
        db.delete(attempt)
        db.commit()


@router.post('/orders/{order_id}/checkout-test', status_code=201)
def start_test_checkout(order_id: int, db: Session = Depends(get_db),
                        user: User = Depends(authenticated_user)):
    _require_sandbox()
    expire_orders(db)
    order = _owned_order(db, order_id, user)
    if order.status != 'reserved' or _aware_utc(order.expires_at) <= utc_now():
        raise HTTPException(409, 'Reserva vencida o no disponible para pagar.')
    existing = db.scalar(select(PaymentAttempt).where(PaymentAttempt.order_id == order.id))
    if existing:
        if existing.checkout_url:
            return {'order_id': order.id, 'provider': existing.provider,
                    'checkout_url': existing.checkout_url, 'status': existing.status,
                    'notice': 'Pago de prueba. Nunca introduzcas una tarjeta real.'}
        if _aware_utc(existing.created_at) > utc_now() - timedelta(minutes=2):
            raise HTTPException(409, 'El pago de prueba ya se está preparando.')
        # Intento abandonado por un proceso interrumpido: se libera para volver a intentar.
        db.delete(existing)
        db.commit()
    reference = f'BP2E-{order.id}-{secrets.token_hex(12)}'
    # El intento se guarda y confirma ANTES de llamar al proveedor: si el webhook
    # llega primero, la referencia ya existe y el pago se puede conciliar.
    attempt = PaymentAttempt(order_id=order.id, reference=reference, provider='mercadopago_sandbox',
                             status='initiated')
    db.add(attempt)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'El pago ya está siendo creado. Actualiza el pedido.') from exc
    try:
        response = create_preference(order, reference, user.email)
    except HTTPException:
        # El proveedor no creó nada que cobrar: el intento se descarta y se puede reintentar.
        _discard_attempt(db, attempt.id)
        raise
    # Solo la dirección SANDBOX; nunca degradar silenciosamente a init_point productivo.
    url = str(response.get('sandbox_init_point') or '')
    if not _safe_checkout_url(url):
        # La preferencia ya existe: se conserva el intento para que el webhook pueda conciliarla.
        raise HTTPException(502, 'El proveedor devolvió una dirección de pago inesperada.')
    attempt.preference_id = str(response.get('id') or '')
    attempt.checkout_url = url
    attempt.status = 'pending'
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'El pago cambió mientras se preparaba. Actualiza el pedido.') from exc
    return {'order_id': order.id, 'provider': attempt.provider, 'checkout_url': url,
            'status': attempt.status, 'notice': 'Pago de prueba. Nunca introduzcas una tarjeta real.'}


def verify_webhook_signature(data_id: str, request_id: str, signature: str) -> bool:
    """Plantilla oficial id:[data.id];request-id:[x-request-id];ts:[ts];"""
    try:
        parts = dict(item.strip().split('=', 1) for item in signature.split(',') if '=' in item)
        ts, signature_hex = parts['ts'], parts['v1']
        timestamp = int(ts)
        # La documentación del proveedor muestra timestamps en segundos y en milisegundos.
        seconds = timestamp / 1000 if timestamp > 100_000_000_000 else timestamp
        if abs(time.time() - seconds) > 600 or len(signature_hex) != 64:
            return False
        template = f'id:{data_id.lower()};request-id:{request_id};ts:{ts};'
        expected = hmac.new(MP_WEBHOOK_SECRET.encode(), template.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature_hex)
    except (KeyError, ValueError, TypeError):
        return False


def _exact_amount(amount, expected: int) -> bool:
    try:
        return Decimal(str(amount)) == Decimal(expected)
    except (ValueError, InvalidOperation, TypeError):
        return False


def _commit_webhook(db: Session) -> None:
    """Confirma la notificación sin exponer un 500 por dos avisos simultáneos del proveedor."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'La notificación ya fue procesada o el pedido cambió.') from exc


@router.post('/payments/mercadopago/webhook')
def receive_webhook(request: Request, db: Session = Depends(get_db)):
    _require_sandbox()
    data_id = request.query_params.get('data.id') or ''
    # Mercado Pago usa `type` en los webhooks y `topic` en el formato IPN anterior.
    topic = request.query_params.get('type') or request.query_params.get('topic') or ''
    request_id = request.headers.get('x-request-id') or ''
    signature = request.headers.get('x-signature') or ''
    if topic != 'payment' or not data_id.isdecimal() or not request_id:
        raise HTTPException(400, 'Notificación de pago inválida.')
    if not verify_webhook_signature(data_id, request_id, signature):
        raise HTTPException(401, 'Firma de notificación inválida.')
    # La firma valida el origen; solo la consulta autenticada confirma el resultado.
    payment = fetch_payment(data_id)
    expire_orders(db)
    live = payment.get('live_mode')
    sandbox_only = live is False or (isinstance(live, str) and live.strip().lower() == 'false')
    if str(payment.get('id')) != data_id or not sandbox_only:
        raise HTTPException(409, 'El pago no pertenece al entorno de pruebas.')
    reference = payment.get('external_reference')
    # Bloqueo de fila: dos notificaciones simultáneas del mismo pago no emiten boletos dos veces.
    attempt = db.scalar(select(PaymentAttempt).where(PaymentAttempt.reference == reference)
                        .with_for_update())
    if not attempt:
        # Notificación válida para otra integración: no revela qué pedidos existen.
        return {'received': True, 'processed': False}
    order = db.scalar(select(PurchaseOrder).options(selectinload(PurchaseOrder.items))
                      .where(PurchaseOrder.id == attempt.order_id).with_for_update())
    if not order or order.currency != payment.get('currency_id') or not _exact_amount(
            payment.get('transaction_amount'), order.subtotal):
        raise HTTPException(409, 'Los datos del pago no corresponden al pedido.')
    if attempt.payment_id and attempt.payment_id != data_id:
        raise HTTPException(409, 'El pedido ya tiene un pago diferente vinculado.')
    if attempt.status == 'late_approved' and attempt.payment_id == data_id:
        return {'received': True, 'processed': False, 'status': 'late_approved'}
    if order.status == 'sandbox_paid' and attempt.payment_id == data_id:
        return {'received': True, 'processed': True, 'status': 'sandbox_paid'}
    if payment.get('status') != 'approved':
        # Pending/rejected no emite boletos ni cambia los contadores de inventario.
        attempt.status = ('pending' if payment.get('status') in ('pending', 'in_process')
                          else 'rejected')
        _commit_webhook(db)
        return {'received': True, 'processed': True, 'status': attempt.status}
    if order.status != 'reserved' or _aware_utc(order.expires_at) <= utc_now():
        # Si el proveedor confirma tarde, se requiere conciliación; no revivir cupos liberados.
        attempt.status = 'late_approved'
        attempt.payment_id = data_id
        db.add(AuditLog(actor_id=None, action='sandbox_payment_late_review_required',
                        target_type='purchase_order', target_id=order.id))
        _commit_webhook(db)
        return {'received': True, 'processed': False, 'status': 'late_approved'}
    _finalize_reserved(db, order, 'sandbox_paid', None, 'sandbox_payment_verified')
    attempt.payment_id = data_id
    attempt.status = 'approved_test'
    _commit_webhook(db)
    return {'received': True, 'processed': True, 'status': 'sandbox_paid'}
