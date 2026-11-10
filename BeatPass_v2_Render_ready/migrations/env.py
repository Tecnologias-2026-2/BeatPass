"""FLUJO: alembic upgrade head -> database.engine -> revisiones en versions/."""
from logging.config import fileConfig
from alembic import context
from backend.database import Base, engine
# Importar todas las tablas para completar metadata.
from backend import models, event_models, inventory_models, order_models  # noqa:F401

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=str(engine.url), target_metadata=target_metadata,
                      literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
