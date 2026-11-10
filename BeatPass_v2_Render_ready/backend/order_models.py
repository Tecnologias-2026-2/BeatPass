"""Fases 2D–2E: reservas, pedidos, intenciones de pago TEST y boletos DEMO.

FLUJO: cart.js -> api.js -> orders.py -> estas tablas -> tickets.js.
"""
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, JSON, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def now_utc():
    return datetime.now(timezone.utc)


class PurchaseOrder(Base):
    __tablename__ = 'purchase_orders'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    status: Mapped[str] = mapped_column(String(24), default='reserved', index=True)
    currency: Mapped[str] = mapped_column(String(3), default='COP')
    subtotal: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items: Mapped[list['PurchaseOrderItem']] = relationship(back_populates='order', cascade='all, delete-orphan')
    payment_attempt: Mapped['PaymentAttempt | None'] = relationship(back_populates='order', uselist=False)
    __table_args__ = (
        CheckConstraint('subtotal >= 0', name='ck_order_subtotal'),
        # Evita dos reservas activas simultáneas del mismo usuario en SQLite y PostgreSQL.
        Index('uq_purchase_order_reserved_user', 'user_id', unique=True,
              sqlite_where=text("status = 'reserved'"),
              postgresql_where=text("status = 'reserved'")),
    )


class PurchaseOrderItem(Base):
    __tablename__ = 'purchase_order_items'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('purchase_orders.id'), index=True)
    inventory_id: Mapped[int] = mapped_column(ForeignKey('ticket_inventory.id'))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    order: Mapped[PurchaseOrder] = relationship(back_populates='items')
    __table_args__ = (CheckConstraint('quantity BETWEEN 1 AND 10', name='ck_order_quantity'),
                        CheckConstraint('unit_price >= 0', name='ck_order_price'),)


class IssuedTicket(Base):
    __tablename__ = 'issued_tickets'
    id: Mapped[int] = mapped_column(primary_key=True)
    public_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey('purchase_order_items.id'), index=True)
    status: Mapped[str] = mapped_column(String(20), default='demo')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    order_item: Mapped[PurchaseOrderItem] = relationship()


class PaymentAttempt(Base):
    """Una intención de pago por reserva. Nunca guarda datos de tarjeta ni secretos."""
    __tablename__ = 'payment_attempts'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('purchase_orders.id'), unique=True, index=True)
    order: Mapped[PurchaseOrder] = relationship(back_populates='payment_attempt')
    provider: Mapped[str] = mapped_column(String(32), default='mercadopago_sandbox')
    reference: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    preference_id: Mapped[str | None] = mapped_column(String(140), nullable=True)
    payment_id: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default='initiated')
    checkout_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
