"""Fase 2E: tablas de pagos de prueba y límite de login."""
from alembic import op
from sqlalchemy import inspect
from backend.database import Base
from backend import models, order_models  # noqa:F401

revision = '0002_payments_and_limiter'
down_revision = '0001_base_2d'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = [Base.metadata.tables['payment_attempts'], Base.metadata.tables['login_throttle']]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)


def downgrade():
    # Solo tablas agregadas en 2E; los pedidos anteriores permanecen.
    bind = op.get_bind()
    Base.metadata.tables['payment_attempts'].drop(bind=bind, checkfirst=True)
    Base.metadata.tables['login_throttle'].drop(bind=bind, checkfirst=True)
