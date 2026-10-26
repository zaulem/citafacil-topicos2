"""Tests de la lógica de reservas y de la API."""
import os
import tempfile

# Usar una base de datos de prueba aislada ANTES de importar la app.
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

from datetime import timedelta  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.utils import PhoneError, local_now, normalize_pa_phone  # noqa: E402

client = TestClient(app)


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


def _next_open_day_at(hour: int):
    d = (local_now() + timedelta(days=1)).replace(hour=hour, minute=0, second=0, microsecond=0)
    while d.weekday() == 6:  # saltar domingo
        d += timedelta(days=1)
    return d


# ---------- Validación de teléfono ----------
def test_phone_valid_formats():
    assert normalize_pa_phone("+507 6123 4567") == "+50761234567"
    assert normalize_pa_phone("50761234567") == "+50761234567"
    assert normalize_pa_phone("0050761234567") == "+50761234567"  # prefijo internacional 00
    assert normalize_pa_phone("6123-4567") == "+50761234567"
    assert normalize_pa_phone("61234567") == "+50761234567"


@pytest.mark.parametrize(
    "raw",
    [
        "12345",            # muy corto
        "+507 2123 4567",   # fijo (no empieza por 6)
        "+507 6123 456",    # 7 dígitos
        "+507 6123 45678",  # 9 dígitos
        "+56 9 4291 6570",  # celular chileno
        "",
    ],
)
def test_phone_invalid(raw):
    with pytest.raises(PhoneError):
        normalize_pa_phone(raw)


# ---------- Reservas ----------
def test_create_and_conflict():
    sid = client.get("/api/services").json()[0]["id"]
    start = _next_open_day_at(11)
    payload = {
        "customer_name": "Camila",
        "customer_phone": "+507 6876 5432",
        "service_id": sid,
        "start_at": start.isoformat(),
    }
    r = client.post("/api/appointments", json=payload)
    assert r.status_code == 201, r.text

    # mismo horario -> 409 (no doble-booking)
    r2 = client.post("/api/appointments", json={**payload, "customer_name": "Otro"})
    assert r2.status_code == 409


def test_availability_removes_booked_slot():
    sid = client.get("/api/services").json()[0]["id"]
    day = _next_open_day_at(11)
    date_str = day.date().isoformat()

    before = client.get(f"/api/availability?service_id={sid}&date={date_str}").json()
    assert "11:00" in before

    client.post(
        "/api/appointments",
        json={
            "customer_name": "Ana",
            "customer_phone": "61234567",
            "service_id": sid,
            "start_at": day.isoformat(),
        },
    )
    after = client.get(f"/api/availability?service_id={sid}&date={date_str}").json()
    assert "11:00" not in after


def test_reject_invalid_phone_on_booking():
    sid = client.get("/api/services").json()[0]["id"]
    start = _next_open_day_at(13)
    r = client.post(
        "/api/appointments",
        json={
            "customer_name": "Mal Tel",
            "customer_phone": "123",
            "service_id": sid,
            "start_at": start.isoformat(),
        },
    )
    assert r.status_code == 422  # falla validación de teléfono


def test_reject_chilean_phone_on_booking():
    sid = client.get("/api/services").json()[0]["id"]
    r = client.post(
        "/api/appointments",
        json={
            "customer_name": "Tel Chile",
            "customer_phone": "+56 9 4291 6570",
            "service_id": sid,
            "start_at": _next_open_day_at(14).isoformat(),
        },
    )
    assert r.status_code == 422
    assert "panameño" in r.json()["detail"][0]["msg"]


# ---------- Localización ----------
def test_config_panama():
    cfg = client.get("/api/config").json()
    assert cfg["timezone"] == "America/Panama"
    assert cfg["currency"] == "USD"


def test_price_in_cents():
    svc = client.get("/api/services").json()[0]
    assert svc["price_cents"] == 1250
    assert "price" not in svc

    r = client.post(
        "/api/admin/services",
        headers={"X-Admin-Token": "test-token"},
        json={"name": "Barba", "duration_min": 20, "price_cents": 650},
    )
    assert r.status_code == 201, r.text
    assert r.json()["price_cents"] == 650


# ---------- Administración ----------
def test_admin_auth():
    assert client.get("/api/admin/appointments").status_code == 422  # falta cabecera
    assert client.get(
        "/api/admin/appointments", headers={"X-Admin-Token": "malo"}
    ).status_code == 401  # token incorrecto
    assert client.get(
        "/api/admin/appointments", headers={"X-Admin-Token": "test-token"}
    ).status_code == 200  # correcto
