"""Modelo mínimo de identidad y revisión de organizadores (2A)."""
# FLUJO: main.py y profile.py guardan usuarios, roles y auditoría con estas tablas.
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def utc_now():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    fullname: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default='active')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_version: Mapped[int] = mapped_column(default=0)
    roles: Mapped[list['UserRole']] = relationship(back_populates='user', cascade='all, delete-orphan')
    organizer_profile: Mapped['OrganizerProfile | None'] = relationship(back_populates='user', uselist=False)

class Role(Base):
    __tablename__ = 'roles'
    code: Mapped[str] = mapped_column(String(35), primary_key=True)
    label: Mapped[str] = mapped_column(String(70))

class UserRole(Base):
    __tablename__ = 'user_roles'
    __table_args__ = (UniqueConstraint('user_id','role_code',name='uq_user_role'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    role_code: Mapped[str] = mapped_column(ForeignKey('roles.code'))
    user: Mapped[User] = relationship(back_populates='roles')

class OrganizerProfile(Base):
    __tablename__ = 'organizer_profiles'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), unique=True)
    display_name: Mapped[str] = mapped_column(String(140))
    phone: Mapped[str] = mapped_column(String(40))
    city: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default='pending')
    user: Mapped[User] = relationship(back_populates='organizer_profile')
    applications: Mapped[list['OrganizerApplication']] = relationship(back_populates='profile')

class OrganizerApplication(Base):
    __tablename__ = 'organizer_applications'
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey('organizer_profiles.id'), index=True)
    status: Mapped[str] = mapped_column(String(30), default='pending', index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile: Mapped[OrganizerProfile] = relationship(back_populates='applications')

class AuthToken(Base):
    __tablename__ = 'auth_tokens'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    purpose: Mapped[str] = mapped_column(String(35), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class AdminInvitation(Base):
    __tablename__ = 'admin_invitations'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    issued_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class LoginThrottle(Base):
    """Contador por identidad HMAC; no guarda correos sin cifrar en esta tabla."""
    __tablename__ = 'login_throttle'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(default=0)
    window_started: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
