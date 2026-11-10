"""Fases 2C–2E: carrito sin reserva; orders.py administra retenciones y pagos de prueba.

Nunca acepta precios del navegador. No hay pago real; las revisiones anteriores quedan desactualizadas.
"""
# FLUJO: pages/cart.html -> js/pages/cart.js -> api.js -> cart.py -> inventory_models.py.
from datetime import date, datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import get_db
from .event_models import Event, EventRevision
from .inventory_models import TicketInventory, CartItem
from .cart_schemas import AddCartItem, SetCartQuantity
from .models import User
from .main import authenticated_user

# Cart.js no envía precio: la API lee zona y precio aprobado desde events.py.
router = APIRouter(prefix='/api', tags=['Inventario y carrito'])
MAX_PER_ZONE = 10


def sync_inventory(db: Session, event: Event, revision: EventRevision) -> None:
    """Una fila por zona aprobada. Repetir la llamada no crea duplicados."""
    for index, zone in enumerate(revision.content.get('ticketTypes', [])):
        existing = db.scalar(select(TicketInventory).where(
            TicketInventory.revision_id == revision.id, TicketInventory.zone_index == index))
        if existing is None:
            db.add(TicketInventory(event_id=event.id, revision_id=revision.id,
                                   zone_index=index, capacity=int(zone.get('capacity') or 0)))
    db.flush()


def _public(db: Session, event_id: int):
    event = db.get(Event, event_id)
    if not event or not event.published_revision_id:
        raise HTTPException(404, 'Evento no disponible para compras.')
    revision = db.get(EventRevision, event.published_revision_id)
    if not revision or revision.status != 'approved':
        raise HTTPException(404, 'Evento no disponible para compras.')
    return event, revision


def _future(revision: EventRevision) -> bool:
    data = revision.content
    zone = ZoneInfo(data.get('timezone', 'America/Bogota'))
    start = datetime.combine(date.fromisoformat(data['date']),
                             datetime.strptime(data['time'][:5], '%H:%M').time(), zone)
    return start > datetime.now(zone)


def _available(inventory: TicketInventory) -> int:
    return max(0, inventory.capacity - inventory.sold - inventory.held)


def _zone(revision: EventRevision, index: int) -> dict:
    zones = revision.content.get('ticketTypes', [])
    if not 0 <= index < len(zones):
        raise HTTPException(404, 'Zona de entradas no encontrada.')
    return zones[index]


def _line(db: Session, item: CartItem) -> dict:
    inventory = item.inventory
    event = db.get(Event, inventory.event_id)
    revision = db.get(EventRevision, inventory.revision_id)
    data = revision.content
    zone = _zone(revision, inventory.zone_index)
    available = _available(inventory)
    status = ('outdated' if event.published_revision_id != revision.id else
              'closed' if not _future(revision) else
              'unavailable' if data.get('seating') == 'Asientos numerados' or available < item.quantity else
              'active')
    price = int(zone['price'])
    return {
        'id': item.id, 'event_id': event.id, 'revision_id': revision.id,
        'event_title': data['title'], 'category': data['category'], 'date': data['date'],
        'time': data['time'][:5], 'venue': data['venue'], 'city': data['city'],
        'zone_index': inventory.zone_index, 'zone_name': zone['name'],
        'unit_price': price, 'quantity': item.quantity, 'line_total': price * item.quantity,
        'available': available, 'status': status,
        'image_url': f'/api/events/{event.id}/cover?v={revision.id}' if event.published_revision_id == revision.id else None,
    }


def _cart(db: Session, user: User) -> dict:
    items = db.scalars(select(CartItem).where(CartItem.user_id == user.id).order_by(CartItem.id)).all()
    rows = [_line(db, item) for item in items]
    # Solo contamos productos vigentes. Una revisión anterior nunca entra en un pedido futuro.
    subtotal = sum(row['line_total'] for row in rows if row['status'] == 'active')
    return {'items': rows, 'subtotal': subtotal, 'currency': 'COP', 'total_items': sum(r['quantity'] for r in rows),
            'has_issues': any(r['status'] != 'active' for r in rows),
            'notice': 'El carrito no aparta cupos. Usa «Reservar 15 minutos» para crear una reserva temporal de demostración.'}


@router.get('/events/{event_id}/availability')
def availability(event_id: int, db: Session = Depends(get_db)):
    from .orders import expire_orders  # FLUJO: libera reservas vencidas antes de mostrar disponibilidad.
    expire_orders(db)
    event, revision = _public(db, event_id)
    future = _future(revision)
    inventories = db.scalars(select(TicketInventory).where(TicketInventory.revision_id == revision.id)
                             .order_by(TicketInventory.zone_index)).all()
    by_index = {row.zone_index: row for row in inventories}
    zones = []
    for i, zone in enumerate(revision.content.get('ticketTypes', [])):
        row = by_index.get(i)
        available = _available(row) if row else 0
        zones.append({'zone_index': i, 'name': zone['name'], 'description': zone.get('description', ''),
                      'price': int(zone['price']), 'capacity': row.capacity if row else 0,
                      'available': available, 'sold': row.sold if row else 0})
    return {'event_id': event.id, 'revision_id': revision.id, 'seating': revision.content['seating'],
            'is_future': future, 'currency': 'COP', 'zones': zones,
            'reservable': future and revision.content['seating'] == 'General por zonas',
            'notice': 'Disponibilidad informativa. Agregar al carrito no aparta entradas.'}


@router.get('/cart')
def get_cart(db: Session = Depends(get_db), user: User = Depends(authenticated_user)):
    from .orders import expire_orders
    expire_orders(db)
    return _cart(db, user)


@router.post('/cart/items', status_code=201)
def add_item(body: AddCartItem, db: Session = Depends(get_db), user: User = Depends(authenticated_user)):
    from .orders import expire_orders
    expire_orders(db)
    event, rev = _public(db, body.event_id)
    if not _future(rev):
        raise HTTPException(409, 'El evento ya comenzó o finalizó.')
    if rev.content.get('seating') != 'General por zonas':
        raise HTTPException(409, 'La selección de asientos numerados se habilitará en una próxima fase.')
    _zone(rev, body.zone_index)
    inventory = db.scalar(select(TicketInventory).where(TicketInventory.revision_id == rev.id,
                          TicketInventory.zone_index == body.zone_index))
    if not inventory:
        raise HTTPException(409, 'Esta zona aún no tiene inventario configurado. El organizador debe publicar una nueva versión con capacidad.')
    if _available(inventory) < body.quantity:
        raise HTTPException(409, 'No hay suficientes boletos disponibles en esta zona.')
    existing = db.scalar(select(CartItem).where(CartItem.user_id == user.id,
                          CartItem.inventory_id == inventory.id))
    if existing:
        # Incremento atómico con límites de unidades y stock; evita el doble clic de los adaptadores antiguos.
        result = db.execute(update(CartItem).where(CartItem.id == existing.id, CartItem.user_id == user.id,
                       CartItem.quantity + body.quantity <= MAX_PER_ZONE,
                       CartItem.quantity + body.quantity <= _available(inventory))
                       .values(quantity=CartItem.quantity + body.quantity))
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(409, 'Superaste el límite de 10 boletos o la disponibilidad de esta zona.')
    else:
        db.add(CartItem(user_id=user.id, inventory_id=inventory.id, quantity=body.quantity))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'El carrito cambió simultáneamente. Actualízalo y vuelve a intentarlo.') from exc
    return _cart(db, user)


@router.patch('/cart/items/{item_id}')
def set_quantity(item_id: int, body: SetCartQuantity, db: Session = Depends(get_db),
                 user: User = Depends(authenticated_user)):
    from .orders import expire_orders
    expire_orders(db)
    item = db.scalar(select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user.id))
    if not item:
        raise HTTPException(404, 'Artículo no encontrado en tu carrito.')
    inventory = item.inventory
    event, rev = _public(db, inventory.event_id)
    if rev.id != inventory.revision_id:
        raise HTTPException(409, 'La publicación cambió: elimina esta entrada y vuelve a añadirla.')
    if not _future(rev) or rev.content.get('seating') != 'General por zonas':
        raise HTTPException(409, 'Esta zona ya no admite nuevas cantidades.')
    if body.quantity > _available(inventory):
        raise HTTPException(409, 'La cantidad supera la disponibilidad actual.')
    db.execute(update(CartItem).where(CartItem.id == item.id, CartItem.user_id == user.id)
               .values(quantity=body.quantity))
    db.commit()
    return _cart(db, user)


@router.delete('/cart/items/{item_id}')
def remove_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(authenticated_user)):
    result = db.execute(delete(CartItem).where(CartItem.id == item_id, CartItem.user_id == user.id))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(404, 'Artículo no encontrado en tu carrito.')
    db.commit()
    return _cart(db, user)


@router.delete('/cart')
def clear_cart(db: Session = Depends(get_db), user: User = Depends(authenticated_user)):
    db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    db.commit()
    return _cart(db, user)
