"""
Configuración de los tests.

core/db_handler.py crea el engine al importarse, leyendo DB_URL del entorno.
En vez de depender del orden de imports para influir en esa lectura, acá se
reemplaza el engine y el sessionmaker de forma explícita después de importar.
Es determinista y deja la intención a la vista: la suite nunca debe tocar
sai_local.db.
"""

import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core import db_handler

_TMP_DB = os.path.join(tempfile.mkdtemp(prefix="sai_tests_"), "test.db")

# Reapuntar la capa de datos a una base temporal.
db_handler.engine = create_engine(f"sqlite:///{_TMP_DB}")
db_handler.Session = sessionmaker(bind=db_handler.engine)
db_handler.Base.metadata.create_all(db_handler.engine)

assert "sai_local.db" not in str(db_handler.engine.url), (
    "La suite quedó apuntando a la base real."
)


@pytest.fixture(autouse=True)
def base_limpia():
    """Cada test arranca con las tablas vacías."""
    session = db_handler.Session()
    try:
        for tabla in reversed(db_handler.Base.metadata.sorted_tables):
            session.execute(tabla.delete())
        session.commit()
    finally:
        session.close()
    yield


@pytest.fixture
def session():
    """Sesión para inspeccionar el estado desde el test."""
    s = db_handler.Session()
    try:
        yield s
    finally:
        s.close()
