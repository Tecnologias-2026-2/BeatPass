"""Entorno seguro para pytest: nunca apunta a la base de datos real.

Cada módulo puede sobrescribir estas variables antes de importar `backend.main`,
pero si una prueba futura lo olvida, aquí queda garantizado un SQLite temporal.
"""
import os
import tempfile
from pathlib import Path

import pytest

_tmp = tempfile.TemporaryDirectory(prefix='beatpass-pytest-')
os.environ['APP_ENV'] = 'local'
os.environ['DATABASE_URL'] = f"sqlite:///{Path(_tmp.name) / 'conftest.db'}"
os.environ['SECRET_KEY'] = 'only-for-isolated-tests-not-for-application-deployment-123456'
os.environ['MAIL_MODE'] = 'development'
os.environ['PAYMENT_MODE'] = 'disabled'


@pytest.fixture(scope='session', autouse=True)
def _release_sqlite_files():
    """Windows no puede borrar la BD temporal mientras el engine siga abierto."""
    yield
    try:
        from backend.database import engine
    except ImportError:
        return
    engine.dispose()

