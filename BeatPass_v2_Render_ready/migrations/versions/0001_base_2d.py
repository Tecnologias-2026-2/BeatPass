"""Adoptar modelo 2D anterior sin borrar datos.

Primer baseline: a partir de aquí, los cambios futuros van en revisiones Alembic.
"""
from alembic import op
from sqlalchemy import inspect, text
from backend.database import Base
from backend import models, event_models, inventory_models, order_models  # noqa:F401

revision = '0001_base_2d'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table('users'):
        columns = {row['name'] for row in inspector.get_columns('users')}
        if 'email_verified_at' not in columns:
            op.execute('ALTER TABLE users ADD COLUMN email_verified_at TIMESTAMP')
        if 'token_version' not in columns:
            op.execute('ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0')
    # Idempotente en instalaciones antiguas que main.init_schema ya inicializó.
    tables = [t for t in Base.metadata.sorted_tables if t.name not in ('payment_attempts', 'login_throttle')]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)


def downgrade():
    raise RuntimeError('No se borra la base 2D ni usuarios al revertir el baseline.')
