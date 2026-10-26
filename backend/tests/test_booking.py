"""Tests de la lógica de reservas y de la API.

La BD de prueba, la configuración fija y el fixture `fresh_db` están en conftest.py.
"""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import models
from app.database import SessionLocal
from app.main import app
from app.utils import PhoneError, local_now, normalize_pa_phone

client = TestClient(app)

# Desde US-01 toda reserva lleva pago (simulado). Tarjeta de prueba aprobada.
PAYMENT = {"card": {"number": "4242 4242 4242 4242", "exp_month": 12, "exp_year": 2030, "cvv": "123"}}


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
        "payment": PAYMENT,
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
            "payment": PAYMENT,
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
            "payment": PAYMENT,
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
            "payment": PAYMENT,
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


# ---------- Calendario mensual (US-02) ----------
def _month_days(sid: int, day) -> dict:
    """Pide el calendario del mes de `day` y devuelve {fecha: {status, free}}."""
    r = client.get(f"/api/availability/month?service_id={sid}&month={day:%Y-%m}")
    assert r.status_code == 200, r.text
    return {d["date"]: d for d in r.json()["days"]}


def test_month_statuses():
    sid = client.get("/api/services").json()[0]["id"]
    today = local_now().date()

    yesterday = today - timedelta(days=1)
    assert _month_days(sid, yesterday)[yesterday.isoformat()]["status"] == "past"

    sunday = today + timedelta(days=(6 - today.weekday()) or 7)
    assert _month_days(sid, sunday)[sunday.isoformat()]["status"] == "closed"

    open_day = _next_open_day_at(11).date()
    entry = _month_days(sid, open_day)[open_day.isoformat()]
    assert entry["status"] == "available"
    assert entry["free"] > 0


def test_month_free_matches_daily_slots():
    sid = client.get("/api/services").json()[0]["id"]
    day = _next_open_day_at(11).date()
    daily = client.get(f"/api/availability?service_id={sid}&date={day.isoformat()}").json()
    assert _month_days(sid, day)[day.isoformat()]["free"] == len(daily)


def test_month_full_day():
    db = SessionLocal()
    long_svc = models.Service(name="Jornada", duration_min=480, price_cents=5000, active=True)
    db.add(long_svc)
    db.commit()
    sid = long_svc.id
    db.close()

    start = _next_open_day_at(10)  # 10:00-18:00 bloquea todos los inicios posibles
    r = client.post(
        "/api/appointments",
        json={"customer_name": "Ana", "customer_phone": "61234567", "service_id": sid, "start_at": start.isoformat(),
              "payment": PAYMENT},
    )
    assert r.status_code == 201, r.text
    entry = _month_days(sid, start.date())[start.date().isoformat()]
    assert entry == {"date": start.date().isoformat(), "status": "full", "free": 0}


def test_booking_horizon():
    sid = client.get("/api/services").json()[0]["id"]
    data = client.get(f"/api/availability/month?service_id={sid}").json()
    beyond = date.fromisoformat(data["max_date"]) + timedelta(days=1)
    while beyond.weekday() == 6:
        beyond += timedelta(days=1)

    assert _month_days(sid, beyond)[beyond.isoformat()]["status"] == "out_of_range"
    assert client.get(f"/api/availability?service_id={sid}&date={beyond.isoformat()}").json() == []
    r = client.post(
        "/api/appointments",
        json={
            "customer_name": "Lejos",
            "customer_phone": "61234567",
            "service_id": sid,
            "start_at": f"{beyond.isoformat()}T11:00:00",
            "payment": PAYMENT,
        },
    )
    assert r.status_code == 409


def test_month_today_uses_business_timezone():
    # H-12: "hoy" lo calcula el backend en la zona del negocio, no el navegador en UTC.
    sid = client.get("/api/services").json()[0]["id"]
    data = client.get(f"/api/availability/month?service_id={sid}").json()
    today = local_now().date()
    assert data["today"] == today.isoformat()
    assert data["month"] == f"{today:%Y-%m}"  # sin parámetro: mes actual


@pytest.mark.parametrize("month", ["2026-13", "2026-1", "noviembre"])
def test_month_invalid(month):
    sid = client.get("/api/services").json()[0]["id"]
    assert client.get(f"/api/availability/month?service_id={sid}&month={month}").status_code == 422


def test_month_unknown_service():
    assert client.get("/api/availability/month?service_id=999").status_code == 404


# ---------- Administración ----------
def test_admin_auth():
    assert client.get("/api/admin/appointments").status_code == 422  # falta cabecera
    assert client.get(
        "/api/admin/appointments", headers={"X-Admin-Token": "malo"}
    ).status_code == 401  # token incorrecto
    assert client.get(
        "/api/admin/appointments", headers={"X-Admin-Token": "test-token"}
    ).status_code == 200  # correcto
