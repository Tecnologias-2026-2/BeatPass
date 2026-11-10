"""Conexión SQLAlchemy. SQLAlchemy con PostgreSQL para el despliegue."""
# FLUJO: main.py / events.py / cart.py / profile.py usan get_db() para guardar en SQLAlchemy.
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import DATABASE_URL

kwargs = {'connect_args': {'check_same_thread': False}} if DATABASE_URL.startswith('sqlite') else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, **kwargs)
if DATABASE_URL.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_foreign_keys(dbapi_conn, _):
        dbapi_conn.execute('PRAGMA foreign_keys=ON')

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    with SessionLocal() as db:
        yield db
