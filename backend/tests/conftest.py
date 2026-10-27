"""Configuración común de los tests. pytest carga este archivo antes que los
módulos de test, así que las variables de entorno quedan fijadas ANTES de que
cualquier test importe la app (si no, se usaría la BD real del .env)."""
import os
import tempfile

# Base de datos de prueba aislada.
# (Se usa el directorio temporal del SO para evitar límites de E/S de
# sistemas de archivos de red; /tmp fijo no existe en Windows.)
_TEST_DB = os.path.join(tempfile.gettempdir(), "citafacil_test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["ADMIN_TOKEN"] = "test-token"
# Configuración del negocio fija: los tests no deben depender del .env local
# de cada integrante (las variables de entorno tienen prioridad sobre el .env).
os.environ["BUSINESS_TIMEZONE"] = "America/Panama"
os.environ["CURRENCY"] = "USD"
os.environ["OPEN_HOUR"] = "10"
os.environ["CLOSE_HOUR"] = "20"
os.environ["SLOT_INTERVAL_MINUTES"] = "30"
os.environ["CLOSED_WEEKDAYS"] = "6"
os.environ["BOOKING_HORIZON_MONTHS"] = "3"
os.environ["CANCEL_MIN_HOURS"] = "24"
os.environ["SESSION_DAYS"] = "7"
os.environ["LOGIN_MAX_ATTEMPTS"] = "5"
os.environ["LOGIN_LOCK_MINUTES"] = "15"

import pytest  # noqa: E402

from app import models  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(models.Service(name="Corte", duration_min=30, price_cents=1250, active=True))
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)
