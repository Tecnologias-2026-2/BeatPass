"""Reservar inventario, confirmar simulación o pago TEST y emitir boletos DEMO.

FLUJO: cart.js -> api.checkoutHold() -> orders.py -> order_models.py.
FLUJO: tickets.js -> api.myTickets() -> orders.py -> boleto/QR privado.
NUNCA se cobra dinero: los boletos DEMO no permiten ingreso real.
"""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import hashlib
import hmac
import secrets
import qrcode
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, selectinload
from .config import SECRET_KEY, DEMO_CHECKOUT_ENABLED
from .database import get_db
from .main import authenticated_user
from .models import AuditLog, User
from .event_models import Event, EventRevision
from .inventory_models import CartItem, TicketInventory
from .order_models import PurchaseOrder, PurchaseOrderItem, IssuedTicket, PaymentAttempt
from .cart import _future, _zone, _public, _available

router = APIRouter(prefix='/api', tags=['Pedidos y boletos demo'])
HOLD_MINUTES = 15
MAX_ORDER_ITEMS = 12


def utc_now():
    return datetime.now(timezone.utc)


def expire_orders(db: Session):
    """Liberación perezosa: corre antes de leer cupos o trabajar con pedidos.

    UPDATE condicionado hace que solo una transacción libere cada pedido.
    En producción a escala añadiremos un worker periódico además de esto.
    """
    expired = db.scalars(select(PurchaseOrder.id).where(
        PurchaseOrder.status == 'reserved', PurchaseOrder.expires_at <= utc_now()).limit(500)).all()
    changed = False
    for order_id in expired:
        claimed = db.execute(update(PurchaseOrder).where(PurchaseOrder.id == order_id,
                   PurchaseOrder.status == 'reserved', PurchaseOrder.expires_at <= utc_now())
                   .values(status='expired'))
        if claimed.rowcount != 1:
            continue
        lines = db.scalars(select(PurchaseOrderItem).where(PurchaseOrderItem.order_id == order_id)).all()
        for line in lines:
            result = db.execute(update(TicketInventory).where(TicketInventory.id == line.inventory_id,
                TicketInventory.held >= line.quantity).values(held=TicketInventory.held - line.quantity))
            if result.rowcount != 1:
                db.rollback()
                raise HTTPException(500, 'No se pudo liberar una reserva caducada.')
        changed = True
    if changed:
        db.commit()
    return changed


def iso_utc(value: datetime | None) -> str | None:
    if value is None: return None
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()


def order_view(order: PurchaseOrder) -> dict:
    return {
        'id': order.id, 'status': order.status, 'currency': order.currency,
        'subtotal': order.subtotal, 'created_at': iso_utc(order.created_at),
        'expires_at': iso_utc(order.expires_at),
        'confirmed_at': iso_utc(order.confirmed_at),
        'demo': True,  # Todos los boletos siguen siendo de prueba, incluso pagando en sandbox.
        'payment': {'status': order.payment_attempt.status, 'provider': order.payment_attempt.provider}
            if order.payment_attempt else None,
        'items': [{'id': line.id, 'quantity': line.quantity, 'unit_price': line.unit_price,
                   'line_total': line.unit_price * line.quantity, **line.snapshot}
                  for line in order.items],
    }


def ticket_view(db: Session, ticket: IssuedTicket):
    line = ticket.order_item
    return {
        'id': ticket.id, 'code': ticket.public_code, 'status': ticket.status,
        'order_id': line.order_id, 'zone_name': line.snapshot['zone_name'],
        'event_title': line.snapshot['event_title'], 'date': line.snapshot['date'],
        'time': line.snapshot['time'], 'venue': line.snapshot['venue'],
        'city': line.snapshot['city'], 'event_id': line.snapshot['event_id'],
        'image_url': line.snapshot['image_url'], 'demo': True,
    }


def _owned_order(db: Session, order_id: int, user: User):
    order = db.scalar(select(PurchaseOrder).options(selectinload(PurchaseOrder.items),
                         selectinload(PurchaseOrder.payment_attempt)).where(PurchaseOrder.id == order_id,
                         PurchaseOrder.user_id == user.id))
    if order is None:
        raise HTTPException(404, 'Pedido no encontrado.')
    return order


def _require_demo():
    if not DEMO_CHECKOUT_ENABLED:
        raise HTTPException(503, 'La confirmación de demostración está desactivada en este entorno.')


@router.get('/checkout/config')
def checkout_config():
    from .payments import sandbox_enabled
    return {'demo_enabled': DEMO_CHECKOUT_ENABLED, 'sandbox_enabled': sandbox_enabled(),
            'hold_minutes': HOLD_MINUTES,
            'notice': 'Simulación académica: no se cobra dinero ni se emiten entradas válidas para el acceso.'}


@router.post('/checkout/hold', status_code=201)
def create_hold(db: Session = Depends(get_db), user: User = Depends(authenticated_user)):
    from .payments import sandbox_enabled
    if not (DEMO_CHECKOUT_ENABLED or sandbox_enabled()):
        raise HTTPException(503, 'Las reservas no están habilitadas.')
    expire_orders(db)
    if db.scalar(select(PurchaseOrder.id).where(
          PurchaseOrder.user_id == user.id, PurchaseOrder.status == 'reserved')) is not None:
        raise HTTPException(409, 'Ya tienes una reserva activa. Confírmala o cancélala primero.')
    cart = db.scalars(select(CartItem).where(CartItem.user_id == user.id).order_by(CartItem.id)).all()
    if not cart or len(cart) > MAX_ORDER_ITEMS:
        raise HTTPException(422, 'El carrito debe tener entre 1 y 12 zonas para reservar.')
    lines = []
    total = 0
    # Validar todo antes de tocar el stock. Solo se procesa la versión publicada.
    for item in cart:
        inv = db.get(TicketInventory, item.inventory_id)
        event, revision = _public(db, inv.event_id)
        if inv.revision_id != revision.id:
            raise HTTPException(409, 'El carrito contiene versiones antiguas de eventos.')
        if not _future(revision) or revision.content['seating'] != 'General por zonas':
            raise HTTPException(409, 'Este evento no admite reservas de zonas generales.')
        if item.quantity > _available(inv):
            raise HTTPException(409, 'La disponibilidad del carrito cambió. Revísalo.')
        zone = _zone(revision, inv.zone_index)
        if item.quantity > 10:
            raise HTTPException(409, 'Máximo diez entradas por zona.')
        price = int(zone['price'])
        snapshot = {'event_id': event.id, 'revision_id': revision.id,
                    'event_title': revision.content['title'], 'date': revision.content['date'],
                    'time': revision.content['time'][:5], 'venue': revision.content['venue'],
                    'city': revision.content['city'], 'zone_name': zone['name'],
                    'image_url': f'/api/events/{event.id}/cover?v={revision.id}'}
        total += price * item.quantity
        lines.append((inv.id, item.quantity, price, snapshot))
    # Comparar capacidad y actualizar held EN SQL: dos compradores no pueden superar el cupo.
    try:
        for inventory_id, quantity, _, _ in sorted(lines):
            affected = db.execute(update(TicketInventory).where(
                TicketInventory.id == inventory_id,
                TicketInventory.capacity - TicketInventory.sold - TicketInventory.held >= quantity)
                .values(held=TicketInventory.held + quantity))
            if affected.rowcount != 1:
                db.rollback()
                raise HTTPException(409, 'Otro usuario reservó las últimas entradas. Actualiza el carrito.')
        order = PurchaseOrder(user_id=user.id, status='reserved', subtotal=total,
                              expires_at=utc_now() + timedelta(minutes=HOLD_MINUTES))
        db.add(order)
        db.flush()
        for inv_id, quantity, price, snapshot in lines:
            db.add(PurchaseOrderItem(order_id=order.id, inventory_id=inv_id,
                                     quantity=quantity, unit_price=price, snapshot=snapshot))
        db.add(AuditLog(actor_id=user.id, action='checkout_hold_created',
                        target_type='purchase_order', target_id=order.id))
        db.commit()
        db.refresh(order)
        return order_view(order)
    except (IntegrityError, OperationalError) as exc:
        db.rollback()
        raise HTTPException(409, 'El inventario cambió. Vuelve a intentar la reserva.') from exc


@router.get('/orders')
def my_orders(db: Session = Depends(get_db), user: User = Depends(authenticated_user)):
    expire_orders(db)
    orders = db.scalars(select(PurchaseOrder).options(selectinload(PurchaseOrder.items),
                      selectinload(PurchaseOrder.payment_attempt)).where(PurchaseOrder.user_id == user.id)
                        .order_by(PurchaseOrder.id.desc()).limit(100)).all()
    return [order_view(order) for order in orders]


@router.get('/orders/{order_id}')
def get_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(authenticated_user)):
    expire_orders(db)
    return order_view(_owned_order(db, order_id, user))


@router.post('/orders/{order_id}/cancel')
def cancel_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(authenticated_user)):
    expire_orders(db)
    order = _owned_order(db, order_id, user)
    claimed = db.execute(update(PurchaseOrder).where(PurchaseOrder.id == order.id,
        PurchaseOrder.status == 'reserved').values(status='cancelled').execution_options(synchronize_session=False))
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'Este pedido no se puede cancelar.')
    for line in order.items:
        changed = db.execute(update(TicketInventory).where(TicketInventory.id == line.inventory_id,
                         TicketInventory.held >= line.quantity)
                         .values(held=TicketInventory.held - line.quantity))
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(500, 'No se pudo liberar el inventario.')
    db.add(AuditLog(actor_id=user.id, action='checkout_hold_cancelled',
                    target_type='purchase_order', target_id=order.id))
    db.commit()
    db.refresh(order)
    return order_view(order)


def _finalize_reserved(db: Session, order: PurchaseOrder, status: str, actor_id: int | None, audit_action: str):
    """FLUJO: confirmación DEMO o webhook TEST -> mismo control atómico de inventario.

    El llamador hace commit. No se emiten entradas reales, solo boletos DEMO.
    """
    current = utc_now()
    claimed = db.execute(update(PurchaseOrder).where(PurchaseOrder.id == order.id,
        PurchaseOrder.status == 'reserved', PurchaseOrder.expires_at > current)
        .values(status=status, confirmed_at=current).execution_options(synchronize_session=False))
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'La reserva venció o ya no puede confirmarse.')
    for line in order.items:
        updated = db.execute(update(TicketInventory).where(TicketInventory.id == line.inventory_id,
            TicketInventory.held >= line.quantity).values(held=TicketInventory.held - line.quantity,
            sold=TicketInventory.sold + line.quantity))
        if updated.rowcount != 1:
            db.rollback()
            raise HTTPException(500, 'No fue posible confirmar el inventario.')
        for _ in range(line.quantity):
            db.add(IssuedTicket(public_code=secrets.token_hex(16).upper(),
                                owner_id=order.user_id, order_item_id=line.id, status='demo'))
        db.execute(delete(CartItem).where(CartItem.user_id == order.user_id,
                   CartItem.inventory_id == line.inventory_id))
    db.add(AuditLog(actor_id=actor_id, action=audit_action,
                    target_type='purchase_order', target_id=order.id))


@router.post('/orders/{order_id}/confirm-demo')
def confirm_demo(order_id: int, db: Session = Depends(get_db), user: User = Depends(authenticated_user)):
    _require_demo()
    expire_orders(db)
    order = _owned_order(db, order_id, user)
    if order.payment_attempt is not None:
        raise HTTPException(409, 'Este pedido está asociado a un pago de prueba; no admite confirmación manual.')
    if order.status == 'demo_confirmed':
        return order_view(order)  # Repetir la petición no duplica los boletos.
    _finalize_reserved(db, order, 'demo_confirmed', user.id, 'checkout_demo_confirmed')
    db.commit()
    db.refresh(order)
    return order_view(order)


@router.get('/tickets')
def my_tickets(db: Session = Depends(get_db), user: User = Depends(authenticated_user)):
    tickets = db.scalars(select(IssuedTicket).options(
                         selectinload(IssuedTicket.order_item)).where(IssuedTicket.owner_id == user.id)
                         .order_by(IssuedTicket.id.desc()).limit(500)).all()
    return [ticket_view(db, ticket) for ticket in tickets]


@router.get('/tickets/{ticket_id}/qr')
def ticket_qr(ticket_id: int, db: Session = Depends(get_db), user: User = Depends(authenticated_user)):
    ticket = db.scalar(select(IssuedTicket).where(IssuedTicket.id == ticket_id,
                       IssuedTicket.owner_id == user.id))
    if not ticket:
        raise HTTPException(404, 'Boleto no encontrado.')
    signature = hmac.new(SECRET_KEY.encode(), ticket.public_code.encode(), hashlib.sha256).hexdigest()
    payload = f'BEATPASS-DEMO:{ticket.public_code}:{signature}'
    image = qrcode.make(payload, box_size=6, border=3)
    output = BytesIO()
    image.save(output, format='PNG')
    return Response(content=output.getvalue(), media_type='image/png',
                    headers={'Cache-Control': 'no-store, private', 'X-Content-Type-Options': 'nosniff'})
