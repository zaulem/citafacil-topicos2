"""Tests del pago simulado y la tarjeta guardada (US-01, parte B)."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import models
from app.database import SessionLocal
from app.main import app
from app.payments import CardError, card_brand, luhn_ok, validate_card
from app.utils import local_now

client = TestClient(app)

VISA = {"number": "4242 4242 4242 4242", "exp_month": 12, "exp_year": 30, "cvv": "123"}
MASTER = {"number": "5555 5555 5555 4444", "exp_month": 1, "exp_year": 2031, "cvv": "321"}
DECLINED = {"number": "4000 0000 0000 0002", "exp_month": 12, "exp_year": 2030, "cvv": "123"}


def _next_open_day_at(hour: int):
    d = (local_now() + timedelta(days=1)).replace(hour=hour, minute=0, second=0, microsecond=0)
    while d.weekday() == 6:  # saltar domingo
        d += timedelta(days=1)
    return d


def _register():
    r = client.post("/api/auth/register", json={
        "email": "ana@correo.com", "password": "Clave-segura-1", "name": "Ana Pérez", "phone": "61234567"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _book(payment, headers=None, hour=11):
    sid = client.get("/api/services").json()[0]["id"]
    return client.post("/api/appointments", headers=headers or {}, json={
        "customer_name": "Ana", "customer_phone": "61234567", "service_id": sid,
        "start_at": _next_open_day_at(hour).isoformat(), "payment": payment})


# ---------- Validación de tarjetas ----------
def test_luhn_and_brand():
    assert luhn_ok("4242424242424242")
    assert not luhn_ok("4242424242424241")
    assert card_brand("4242424242424242") == "Visa"
    assert card_brand("5555555555554444") == "Mastercard"
    assert card_brand("2223003122003222") == "Mastercard"  # rango 2221-2720
    assert card_brand("378282246310005") == "Amex"
    assert card_brand("6011111111111117") is None  # Discover: no aceptada


@pytest.mark.parametrize(
    "number, month, year, cvv, error",
    [
        ("4242 4242 4242 4241", 12, 2030, "123", "inválido"),     # falla Luhn
        ("6011 1111 1111 1117", 12, 2030, "123", "no reconocida"),
        ("4242 4242 4242 abcd", 12, 2030, "123", "dígitos"),
        ("4242 4242 4242 4242", 1, 2020, "123", "vencida"),
        ("4242 4242 4242 4242", 12, 2030, "12", "CVV"),
        ("3782 822463 10005", 12, 2030, "123", "4 dígitos"),     # Amex usa CVV de 4
    ],
)
def test_validate_card_errors(number, month, year, cvv, error):
    with pytest.raises(CardError, match=error):
        validate_card(number, month, year, cvv)


def test_validate_card_normalizes():
    assert validate_card("4242-4242-4242-4242", 12, 30, "123") == ("4242424242424242", "Visa", 2030)


# ---------- Reserva con pago ----------
def test_guest_pays_with_card_and_only_last4_is_stored():
    r = _book({"card": VISA})
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["payment_status"] == "paid"
    assert a["price_paid_cents"] == 1250
    assert (a["payment_brand"], a["payment_last4"]) == ("Visa", "4242")

    # Ninguna columna de la BD contiene el número completo, y no existe columna para el CVV.
    db = SessionLocal()
    appt = db.query(models.Appointment).one()
    values = " ".join(str(getattr(appt, c.name)) for c in models.Appointment.__table__.columns)
    db.close()
    assert "4242424242424242" not in values
    for table in (models.Appointment.__table__, models.PaymentMethod.__table__):
        assert not any("cvv" in c.name or c.name == "number" for c in table.columns)


def test_payment_required():
    sid = client.get("/api/services").json()[0]["id"]
    r = client.post("/api/appointments", json={
        "customer_name": "Ana", "customer_phone": "61234567", "service_id": sid,
        "start_at": _next_open_day_at(11).isoformat()})
    assert r.status_code == 422


def test_invalid_card_rejected_on_booking():
    r = _book({"card": {**VISA, "number": "4242 4242 4242 4241"}})
    assert r.status_code == 422
    assert "inválido" in r.json()["detail"][0]["msg"]


def test_declined_card_creates_no_appointment():
    r = _book({"card": DECLINED})
    assert r.status_code == 402
    assert "rechazado" in r.json()["detail"]
    db = SessionLocal()
    assert db.query(models.Appointment).count() == 0
    db.close()


def test_price_paid_kept_when_service_price_changes():
    # H-15: el histórico no cambia si después cambia el precio del servicio.
    appt_id = _book({"card": VISA}).json()["id"]
    sid = client.get("/api/services").json()[0]["id"]
    client.put(f"/api/admin/services/{sid}", headers={"X-Admin-Token": "test-token"}, json={"price_cents": 2000})
    appts = client.get("/api/admin/appointments", headers={"X-Admin-Token": "test-token"}).json()
    assert next(a for a in appts if a["id"] == appt_id)["price_paid_cents"] == 1250


# ---------- Tarjeta guardada ----------
def test_save_card_while_booking_then_pay_with_saved_card():
    h = _register()
    r = _book({"card": VISA, "save_card": True}, headers=h)
    assert r.status_code == 201, r.text
    assert client.get("/api/me/card", headers=h).json() == {
        "brand": "Visa", "last4": "4242", "exp_month": 12, "exp_year": 2030}

    r2 = _book({"use_saved_card": True}, headers=h, hour=13)  # sin datos de tarjeta
    assert r2.status_code == 201, r2.text
    assert (r2.json()["payment_status"], r2.json()["payment_last4"]) == ("paid", "4242")


def test_one_card_per_customer_replaces_previous():
    h = _register()
    assert client.put("/api/me/card", headers=h, json=VISA).status_code == 200
    r = client.put("/api/me/card", headers=h, json=MASTER)
    assert r.json()["last4"] == "4444"
    db = SessionLocal()
    assert db.query(models.PaymentMethod).count() == 1
    db.close()


def test_saved_card_requires_session():
    assert _book({"use_saved_card": True}).status_code == 401
    assert _book({"card": VISA, "save_card": True}).status_code == 401
    assert client.get("/api/me/card").status_code == 401


def test_use_saved_card_without_card():
    h = _register()
    r = _book({"use_saved_card": True}, headers=h)
    assert r.status_code == 400
    assert client.get("/api/me/card", headers=h).status_code == 404


def test_payment_needs_exactly_one_source():
    assert _book({}).status_code == 422                                    # ninguna
    assert _book({"use_saved_card": True, "card": VISA}).status_code == 422  # ambas


def test_delete_card():
    h = _register()
    client.put("/api/me/card", headers=h, json=VISA)
    assert client.delete("/api/me/card", headers=h).status_code == 200
    assert client.get("/api/me/card", headers=h).status_code == 404
    assert client.delete("/api/me/card", headers=h).status_code == 404
