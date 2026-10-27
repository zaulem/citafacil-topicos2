"""Reglas de estado de las citas y cruce entre acciones del admin y del cliente (H-30 a H-35)."""
from datetime import date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.utils import local_now

client = TestClient(app)
ADMIN = {"X-Admin-Token": "test-token"}
CARD = {"number": "4242 4242 4242 4242", "exp_month": 12, "exp_year": 2030, "cvv": "123"}


def _open_day(days_ahead: int) -> date:
    d = local_now().date() + timedelta(days=days_ahead)
    while d.weekday() == 6:
        d += timedelta(days=1)
    return d


def _at(day: date, hour: int) -> str:
    return datetime.combine(day, time(hour=hour)).isoformat()


def _register(email="ana@correo.com"):
    r = client.post("/api/auth/register", json={
        "email": email, "password": "Clave-segura-1", "name": "Ana Pérez", "phone": "61234567"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _book(headers, start_iso):
    sid = client.get("/api/services").json()[0]["id"]
    r = client.post("/api/appointments", headers=headers, json={
        "customer_name": "Ana", "customer_phone": "61234567", "service_id": sid,
        "start_at": start_iso, "payment": {"card": CARD}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _admin_set(appt_id, status):
    return client.patch(f"/api/admin/appointments/{appt_id}", headers=ADMIN, json={"status": status})


def _mine(headers, appt_id):
    data = client.get("/api/me/appointments", headers=headers).json()
    return data, next(a for a in data["appointments"] if a["id"] == appt_id)


# ---------- Admin marca Realizada (H-30) ----------
def test_admin_done_is_reflected_for_client_and_blocks_changes():
    h = _register()
    appt_id = _book(h, _at(_open_day(3), 11))
    assert _admin_set(appt_id, "done").status_code == 200

    data, a = _mine(h, appt_id)
    assert (a["state"], a["can_change"]) == ("done", False)
    assert data["counts"]["done"] == 1 and data["counts"]["scheduled"] == 0
    assert client.post(f"/api/me/appointments/{appt_id}/cancel", headers=h).status_code == 409
    r = client.post(f"/api/me/appointments/{appt_id}/reschedule", headers=h,
                    json={"start_at": _at(_open_day(5), 15)})
    assert r.status_code == 409


# ---------- Admin cancela: reembolso (H-31) ----------
def test_admin_cancel_refunds_payment():
    h = _register()
    appt_id = _book(h, _at(_open_day(3), 11))
    r = _admin_set(appt_id, "cancelled")
    assert r.status_code == 200
    assert (r.json()["status"], r.json()["payment_status"]) == ("cancelled", "refunded")
    assert _mine(h, appt_id)[1]["state"] == "cancelled"


# ---------- Cancelada y Realizada son finales (H-32) ----------
def test_cancelled_cannot_be_reactivated_so_no_double_booking():
    h = _register()
    day = _open_day(3)
    appt_id = _book(h, _at(day, 11))
    assert client.post(f"/api/me/appointments/{appt_id}/cancel", headers=h).status_code == 200
    other = _book(_register("otro@correo.com"), _at(day, 11))   # otro cliente toma el horario liberado

    for status in ("confirmed", "pending", "done"):
        r = _admin_set(appt_id, status)
        assert r.status_code == 409 and "cancelada no puede pasar" in r.json()["detail"]
    admin = {a["id"]: a for a in client.get("/api/admin/appointments", headers=ADMIN).json()}
    assert admin[appt_id]["status"] == "cancelled" and admin[other]["status"] == "pending"


@pytest.mark.parametrize("status", ["pending", "confirmed", "cancelled"])
def test_done_is_final(status):
    appt_id = _book(_register(), _at(_open_day(3), 11))
    assert _admin_set(appt_id, "done").status_code == 200
    assert _admin_set(appt_id, status).status_code == 409


def test_valid_transitions_and_same_status():
    appt_id = _book(_register(), _at(_open_day(3), 11))
    assert _admin_set(appt_id, "pending").status_code == 200      # mismo estado: sin cambios
    assert _admin_set(appt_id, "confirmed").status_code == 200
    assert _admin_set(appt_id, "pending").status_code == 409      # no se vuelve atrás
    assert _admin_set(appt_id, "done").json()["status"] == "done"


# ---------- Estadísticas coherentes con Reservas y Mis reservas (H-35) ----------
def test_stats_count_admin_done_as_done_and_reconcile():
    h = _register()
    done_early = _book(h, _at(_open_day(3), 11))
    _book(h, _at(_open_day(4), 11))
    _admin_set(done_early, "done")

    real = client.get("/api/admin/forecast", headers=ADMIN, params={
        "start": local_now().date().isoformat(), "end": _open_day(10).isoformat()}).json()["real"]["kpis"]
    stats = client.get("/api/admin/stats", headers=ADMIN).json()
    assert (real["done"], real["booked"]) == (1, 1)
    assert real["booked"] == stats["upcoming"]          # próximas = pendientes/confirmadas futuras
    assert real["registered"] + real["cancelled"] == real["total"] == stats["total"]
