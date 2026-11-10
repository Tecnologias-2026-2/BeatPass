"""Fase 2B: editor, revisiones, aprobación y lectura pública de eventos.

Invariante: solo `Event.published_revision_id` expone datos públicamente.
Cada modificación posterior queda aislada hasta una nueva aprobación.
"""
# FLUJO: admin-events.js / admin-event-reviews.js -> api.js -> events.py -> event_models.py.
from datetime import date, datetime, timezone
from io import BytesIO
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select, update, func, or_
from sqlalchemy.orm import Session
from .database import get_db
from .models import User, AuditLog
from .event_models import Event, EventRevision, EventCover
from .event_schemas import EventData, EventDecision
from .inventory_models import TicketInventory
from .main import authenticated_user, require_admin, roles

# Panel y catálogo usan el mismo router: nunca exponemos revisiones sin aprobación.
router = APIRouter(prefix='/api', tags=['Eventos y aprobación'])
MAX_COVER_BYTES = 3 * 1024 * 1024


def require_organizer(user: User = Depends(authenticated_user)) -> User:
    if 'organizador' not in roles(user) and 'administracion' not in roles(user):
        raise HTTPException(403, 'Solo un organizador aprobado o un administrador puede crear eventos.')
    return user


def _latest(db: Session, event_id: int) -> EventRevision | None:
    return db.scalar(select(EventRevision).where(EventRevision.event_id == event_id)
                     .order_by(EventRevision.version.desc()).limit(1))


def _owned(db: Session, event_id: int, user: User) -> Event:
    event = db.get(Event, event_id)
    if not event or event.organizer_id != user.id:
        raise HTTPException(404, 'Evento no encontrado entre tus eventos.')
    return event


def _edit_revision(db: Session, event: Event) -> EventRevision:
    rev = _latest(db, event.id)
    if not rev:
        raise HTTPException(500, 'El evento no tiene revisión.')
    if rev.status == 'pending':
        raise HTTPException(409, 'Este evento está pendiente de revisión; no puedes modificarlo todavía.')
    if rev.status in ('draft', 'rejected'):
        return rev
    # Copiar lo que ya está aprobado a una NUEVA revisión; nunca modificar el público.
    revision = EventRevision(event_id=event.id, version=rev.version + 1,
                             status='draft', content=dict(rev.content))
    db.add(revision)
    db.flush()
    cover = db.get(EventCover, event.published_revision_id) if event.published_revision_id else None
    if cover:
        db.add(EventCover(revision_id=revision.id, mime_type=cover.mime_type, data=cover.data))
    return revision


def _has_cover(db: Session, revision_id: int) -> bool:
    return db.get(EventCover, revision_id) is not None


def _summary(event: Event, rev: EventRevision, db: Session, *, public: bool = False,
             cover_exists: bool | None = None) -> dict:
    data = rev.content
    prices = data.get('ticketTypes', [])
    has_cover = _has_cover(db, rev.id) if cover_exists is None else cover_exists
    return {
        'id': event.id, 'revision_id': rev.id, 'version': rev.version,
        'status': 'published' if public else rev.status,
        'published': event.published_revision_id is not None,
        'title': data['title'], 'category': data['category'], 'short': data['short'],
        'description': data['description'], 'date': data['date'], 'time': data['time'][:5],
        'venue': data['venue'], 'city': data['city'], 'address': data['address'],
        'seating': data['seating'], 'timezone': data.get('timezone','America/Bogota'), 'ticketTypes': prices,
        'minPrice': min(zone['price'] for zone in prices), 'currency': 'COP',
        'hasCover': has_cover,
        'image_url': f'/api/events/{event.id}/cover?v={rev.id}' if public and has_cover else None,
        'review_reason': None if public else rev.review_reason,
        'organizer_id': event.organizer_id,
    }


@router.get('/events')
def public_events(db: Session = Depends(get_db), q: str = Query(default='', max_length=120),
                  category: str = Query(default='', max_length=30),
                  limit: int = Query(default=24, ge=1, le=100), offset: int = Query(default=0, ge=0, le=100000)):
    """Filtrar en SQL antes de paginar: no perder coincidencias detrás de los primeros 200."""
    stmt = select(Event, EventRevision).join(EventRevision,
        Event.published_revision_id == EventRevision.id).where(EventRevision.status == 'approved')
    if category:
        stmt = stmt.where(func.lower(EventRevision.content['category'].as_string()) == category.lower())
    if q:
        # Escapar comodines LIKE para buscar texto literal, no patrones del navegador.
        escaped = q.strip().lower().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        term = '%' + escaped + '%'
        stmt = stmt.where(or_(*(func.lower(EventRevision.content[field].as_string()).like(
            term, escape='\\') for field in ('title', 'city', 'venue', 'short'))))
    rows = db.execute(stmt.order_by(Event.id.desc()).offset(offset).limit(limit)).all()
    cover_ids = set(db.scalars(select(EventCover.revision_id).where(
        EventCover.revision_id.in_([rev.id for _, rev in rows]))).all()) if rows else set()
    return [_summary(event, rev, db, public=True, cover_exists=rev.id in cover_ids)
            for event, rev in rows]


@router.get('/events/{event_id}')
def public_event(event_id: int, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event or not event.published_revision_id:
        raise HTTPException(404, 'Este evento no está publicado.')
    rev = db.get(EventRevision, event.published_revision_id)
    if not rev or rev.status != 'approved':
        raise HTTPException(404, 'Este evento no está publicado.')
    return _summary(event, rev, db, public=True)


@router.get('/events/{event_id}/cover')
def public_cover(event_id: int, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event or not event.published_revision_id:
        raise HTTPException(404, 'Portada no disponible.')
    cover = db.get(EventCover, event.published_revision_id)
    if not cover:
        raise HTTPException(404, 'Portada no disponible.')
    return Response(content=cover.data, media_type=cover.mime_type,
                    headers={'Cache-Control': 'public, max-age=3600', 'X-Content-Type-Options': 'nosniff'})


@router.get('/organizers/events')
def my_events(db: Session = Depends(get_db), owner: User = Depends(require_organizer)):
    events = db.scalars(select(Event).where(Event.organizer_id == owner.id).order_by(Event.created_at.desc())).all()
    return [_summary(event, _latest(db, event.id), db) for event in events]


@router.post('/organizers/events', status_code=201)
def create_event(body: EventData, db: Session = Depends(get_db), owner: User = Depends(require_organizer)):
    event = Event(organizer_id=owner.id)
    db.add(event)
    db.flush()
    revision = EventRevision(event_id=event.id, version=1, content=body.model_dump(mode='json'))
    db.add(revision)
    db.add(AuditLog(actor_id=owner.id, action='event_created', target_type='event', target_id=event.id))
    db.commit()
    db.refresh(revision)
    return _summary(event, revision, db)


@router.get('/organizers/events/{event_id}')
def my_event(event_id: int, db: Session = Depends(get_db), owner: User = Depends(require_organizer)):
    event = _owned(db, event_id, owner)
    return _summary(event, _latest(db, event.id), db)


@router.put('/organizers/events/{event_id}')
def save_event(event_id: int, body: EventData, db: Session = Depends(get_db), owner: User = Depends(require_organizer)):
    event = _owned(db, event_id, owner)
    revision = _edit_revision(db, event)
    revision.content = body.model_dump(mode='json')
    revision.status = 'draft'
    revision.review_reason = None
    db.add(AuditLog(actor_id=owner.id, action='event_draft_saved', target_type='event', target_id=event.id))
    db.commit()
    return _summary(event, revision, db)


@router.post('/organizers/events/{event_id}/cover')
async def save_cover(event_id: int, request: Request, db: Session = Depends(get_db),
                     owner: User = Depends(require_organizer)):
    event = _owned(db, event_id, owner)
    # Nunca crear nueva revisión mediante subida de imagen. Primero guardar los datos del borrador.
    latest = _latest(db, event.id)
    if latest.status != 'draft':
        raise HTTPException(409, 'Guarda o crea primero un borrador editable para subir su portada.')
    if request.headers.get('content-length') and int(request.headers['content-length']) > MAX_COVER_BYTES:
        raise HTTPException(413, 'La fotografía optimizada supera el límite de 3 MB.')
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_COVER_BYTES:
            raise HTTPException(413, 'La portada optimizada supera el límite de 3 MB.')
        content.extend(chunk)
    if not content:
        raise HTTPException(422, 'El archivo de imagen está vacío.')
    raw = bytes(content)
    try:
        with Image.open(BytesIO(raw)) as image:
            if image.format not in ('JPEG', 'PNG', 'WEBP') or image.width * image.height > 40_000_000:
                raise ValueError('Formato o tamaño no permitido')
            image.thumbnail((1600, 1600))
            canvas = image.convert('RGB')
            stream = BytesIO()
            canvas.save(stream, format='JPEG', quality=82, optimize=True)
            normalized = stream.getvalue()
            if len(normalized) > MAX_COVER_BYTES:
                raise ValueError('La fotografía es demasiado grande')
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, 'Sube una imagen JPG, PNG o WebP válida, de máximo 8 MB en origen.') from exc
    cover = db.get(EventCover, latest.id)
    if cover:
        cover.data = normalized
        cover.mime_type = 'image/jpeg'
    else:
        db.add(EventCover(revision_id=latest.id, mime_type='image/jpeg', data=normalized))
    db.commit()
    return {'message': 'Portada guardada en el servidor.', 'revision_id': latest.id}


@router.get('/organizers/events/{event_id}/cover')
def my_cover(event_id: int, db: Session = Depends(get_db), owner: User = Depends(require_organizer)):
    event = _owned(db, event_id, owner)
    latest = _latest(db, event.id)
    cover = db.get(EventCover, latest.id)
    if not cover:
        raise HTTPException(404, 'Borrador sin portada.')
    return Response(content=cover.data, media_type=cover.mime_type,
                    headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


@router.delete('/organizers/events/{event_id}/cover')
def delete_cover(event_id: int, db: Session = Depends(get_db), owner: User = Depends(require_organizer)):
    event = _owned(db, event_id, owner)
    rev = _latest(db, event.id)
    if rev.status != 'draft':
        raise HTTPException(409, 'La portada de una revisión enviada o aprobada no se puede eliminar.')
    cover = db.get(EventCover, rev.id)
    if cover:
        db.delete(cover)
        db.commit()
    return {'message': 'Portada eliminada.'}


@router.post('/organizers/events/{event_id}/submit')
def submit_event(event_id: int, db: Session = Depends(get_db), owner: User = Depends(require_organizer)):
    event = _owned(db, event_id, owner)
    rev = _latest(db, event.id)
    if rev.status != 'draft':
        raise HTTPException(409, 'Solo se puede enviar un borrador. Edita el evento antes de reenviarlo.')
    event_zone = ZoneInfo(rev.content.get('timezone','America/Bogota'))
    if datetime.combine(date.fromisoformat(rev.content['date']), datetime.strptime(rev.content['time'][:5], '%H:%M').time(), event_zone) <= datetime.now(event_zone):
        raise HTTPException(422, 'La fecha del evento no puede estar en el pasado.')
    # Actualización condicional: dos peticiones simultáneas no envían dos veces el mismo borrador.
    outcome = db.execute(update(EventRevision).where(EventRevision.id == rev.id,
                   EventRevision.status == 'draft').values(status='pending', submitted_at=datetime.now(timezone.utc)))
    if outcome.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'Este borrador ya fue enviado.')
    db.add(AuditLog(actor_id=owner.id, action='event_submitted', target_type='event_revision', target_id=rev.id))
    db.commit()
    return {'message': 'Evento enviado a revisión. No será visible hasta la aprobación.', 'revision_id': rev.id}


@router.get('/admin/events/reviews')
def pending_event_reviews(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    pending = db.scalars(select(EventRevision).where(EventRevision.status == 'pending')
                         .order_by(EventRevision.submitted_at.asc())).all()
    result = []
    for rev in pending:
        event = db.get(Event, rev.event_id)
        owner = db.get(User, event.organizer_id)
        row = _summary(event, rev, db)
        row['organizer_name'] = owner.fullname
        row['organizer_email'] = owner.email
        result.append(row)
    return result



@router.get('/admin/events/reviews/{revision_id}/cover')
def review_cover(revision_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    revision = db.get(EventRevision, revision_id)
    if not revision or revision.status != 'pending':
        raise HTTPException(404, 'La revisión no está pendiente.')
    cover = db.get(EventCover, revision_id)
    if not cover:
        raise HTTPException(404, 'La propuesta no tiene portada.')
    return Response(content=cover.data, media_type=cover.mime_type,
                    headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

def _review_event(revision_id: int, decision: str, body: EventDecision, db: Session, admin: User):
    rev = db.get(EventRevision, revision_id)
    if not rev:
        raise HTTPException(404, 'Revisión no encontrada.')
    event = db.get(Event, rev.event_id)
    if event.organizer_id == admin.id:
        raise HTTPException(403, 'No puedes revisar tus propios eventos.')
    if decision == 'approved' and datetime.combine(date.fromisoformat(rev.content['date']), datetime.strptime(rev.content['time'][:5], '%H:%M').time(), ZoneInfo(rev.content.get('timezone','America/Bogota'))) <= datetime.now(ZoneInfo(rev.content.get('timezone','America/Bogota'))):
        raise HTTPException(422, 'Este evento ya tiene una fecha pasada: debe corregirse antes de publicarse.')
    if decision == 'rejected' and not body.reason.strip():
        raise HTTPException(422, 'Escribe el motivo de rechazo.')
    outcome = db.execute(update(EventRevision).where(EventRevision.id == revision_id,
         EventRevision.status == 'pending').values(status=decision, review_reason=body.reason.strip() or None,
         reviewer_id=admin.id, reviewed_at=datetime.now(timezone.utc)))
    if outcome.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'Este evento ya fue revisado.')
    if decision == 'approved':
        # Protección para fases futuras: una revisión nueva no puede reiniciar ventas/retenciones existentes.
        if event.published_revision_id and event.published_revision_id != rev.id:
            previous = db.scalars(select(TicketInventory).where(
                TicketInventory.revision_id == event.published_revision_id).with_for_update()).all()
            if any(row.sold or row.held for row in previous):
                db.rollback()
                raise HTTPException(409, 'Este evento tiene entradas vendidas o retenidas. Para aprobar una nueva versión se necesita una migración de inventario segura.')
        from .cart import sync_inventory
        sync_inventory(db, event, rev)
        event.published_revision_id = revision_id
    db.add(AuditLog(actor_id=admin.id, action=f'event_{decision}',
                    target_type='event_revision', target_id=revision_id))
    db.commit()
    return {'message': 'Evento aprobado y publicado.' if decision == 'approved' else 'Revisión rechazada; el evento no se ha publicado.',
            'revision_id': revision_id, 'status': decision}


@router.post('/admin/events/reviews/{revision_id}/approve')
def approve_event(revision_id: int, body: EventDecision, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return _review_event(revision_id, 'approved', body, db, admin)


@router.post('/admin/events/reviews/{revision_id}/reject')
def reject_event(revision_id: int, body: EventDecision, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return _review_event(revision_id, 'rejected', body, db, admin)
