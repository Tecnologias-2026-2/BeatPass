"""Entidades de eventos y revisiones. Solo la revisión aprobada es pública."""
# FLUJO: events.py lee/escribe Event, EventRevision y EventCover en database.py.
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String, Integer, DateTime, JSON, LargeBinary, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


def timestamp():
    return datetime.now(timezone.utc)


class Event(Base):
    __tablename__ = 'events'
    id: Mapped[int] = mapped_column(primary_key=True)
    organizer_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    published_revision_id: Mapped[int | None] = mapped_column(ForeignKey('event_revisions.id', use_alter=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=timestamp)


class EventRevision(Base):
    __tablename__ = 'event_revisions'
    __table_args__ = (UniqueConstraint('event_id', 'version', name='uq_event_revision_version'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey('events.id'), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default='draft', index=True)
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=timestamp)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class EventCover(Base):
    __tablename__ = 'event_covers'
    revision_id: Mapped[int] = mapped_column(ForeignKey('event_revisions.id'), primary_key=True)
    mime_type: Mapped[str] = mapped_column(String(40), default='image/jpeg')
    data: Mapped[bytes] = mapped_column(LargeBinary)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=timestamp, onupdate=timestamp)
