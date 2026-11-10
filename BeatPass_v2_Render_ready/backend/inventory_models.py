"""Inventario aprobado por revisión y carrito persistente por usuario.

El carrito NO reserva; orders.py actualiza held/sold durante la fase 2D.
"""
# FLUJO: cart.py guarda inventario aprobado y carrito usando estas tablas.
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def utc_now():
    return datetime.now(timezone.utc)


class TicketInventory(Base):
    __tablename__ = 'ticket_inventory'
    __table_args__ = (
        UniqueConstraint('revision_id', 'zone_index', name='uq_inventory_revision_zone'),
        CheckConstraint('capacity >= 0', name='ck_inventory_capacity'),
        CheckConstraint('sold >= 0 AND held >= 0 AND sold + held <= capacity', name='ck_inventory_counts'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey('events.id'), index=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey('event_revisions.id'), index=True)
    zone_index: Mapped[int] = mapped_column(Integer)
    capacity: Mapped[int] = mapped_column(Integer)
    sold: Mapped[int] = mapped_column(Integer, default=0)
    held: Mapped[int] = mapped_column(Integer, default=0)


class CartItem(Base):
    __tablename__ = 'cart_items'
    __table_args__ = (
        UniqueConstraint('user_id', 'inventory_id', name='uq_cart_user_inventory'),
        CheckConstraint('quantity BETWEEN 1 AND 10', name='ck_cart_quantity'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    inventory_id: Mapped[int] = mapped_column(ForeignKey('ticket_inventory.id'), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    inventory: Mapped[TicketInventory] = relationship()
