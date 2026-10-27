"""Tests de Mis reservas (US-05): ver, cancelar (con reembolso) y reprogramar."""
from datetime import date, datetime, time, timedelta

from fastapi.testclient import TestClient

from app import models
from app.database import SessionLocal
from app.main import app
from app.utils import local_now

client = TestClient(app)
CARD = {"number": "4242 4242 4242 4242", "exp_month": 12, "exp_year": 2030, "cvv": "123"}
ADMIN = {"X-Admin-Token": "test-token"}


def _open_day(days_ahead: int) -> date:
    """Primer día abierto a partir de `days_ahead` días desde hoy (salta domingos)."""
    d = local_now().date() + timedelta(days=days_ahead)
    while d.weekday() == 6:
        d += timedelta(days=1)
    return d


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour=hour, minute=minute))


def _register(email="ana@correo.com"):
    r = client.post("/api/auth/register", json={
        "email": email, "password": "Clave-segura-1", "name": "Ana Pérez", "phone": "61234567"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["customer"]["id"]


def _service(name="Corte", minutes=30):
    db = SessionLocal()
    svc = db.query(models.Service).filter_by(name=name).first()
    if not svc:
        svc = models.Service(name=name, duration_min=minutes, price_cents=1800, active=True)
        db.add(svc)
        db.commit()
    sid = svc.id
    db.close()
    return sid


def _book(headers, start: datetime, service="Corte", minutes=30):
    r = client.post("/api/appointments", headers=headers, json={
        "customer_name": "Ana", "customer_phone": "61234567", "service_id": _service(service, minutes),
        "start_at": start.isoformat(), "payment": {"card": CARD}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _insert(customer_id, start: datetime, status=models.STATUS_CONFIRMED):
    """Cita directa en la BD (para fechas que la API no permite reservar: pasadas o < 24 h)."""
    db = SessionLocal()
    appt = models.Appointment(
        customer_id=customer_id, customer_name="Ana", customer_phone="+50761234567",
        service_id=_service(), start_at=start, end_at=start + timedelta(minutes=30), status=status,
        payment_status=models.PAYMENT_PAID, price_paid_cents=1250, created_at=start - timedelta(days=2))
    db.add(appt)
    db.commit()
    appt_id = appt.id
    db.close()
    return appt_id


def _slots(day: date, service="Corte", headers=None, exclude_id=None):
    params = {"service_id": _service(service), "date": day.isoformat()}
    if exclude_id:
        params["exclude_id"] = exclude_id
    return client.get("/api/availability", params=params, headers=headers or {}).json()


# ---------- Ver mis reservas ----------
def test_my_appointments_requires_session():
    assert client.get("/api/me/appointments").status_code == 401


def test_list_counts_and_states():
    h, cid = _register()
    future = _book(h, _at(_open_day(3), 11))
    _insert(cid, _at(_open_day(-10), 11), status=models.STATUS_DONE)          # completada
    _insert(cid, _at(_open_day(5), 15), status=models.STATUS_CANCELLED)       # cancelada
    other_h, _ = _register("otro@correo.com")
    _book(other_h, _at(_open_day(3), 13))                                     # de otro cliente

    data = client.get("/api/me/appointments", headers=h).json()
    assert data["counts"] == {"total": 3, "scheduled": 1, "done": 1, "cancelled": 1}
    assert data["cancel_min_hours"] == 24
    mine = {a["id"]: a for a in data["appointments"]}
    assert mine[future]["state"] == "scheduled" and mine[future]["can_change"] is True
    assert all(not a["can_change"] for a in data["appointments"] if a["id"] != future)


# ---------- Cancelar ----------
def test_cancel_refunds_and_frees_slot():
    h, _ = _register()
    day = _open_day(3)
    appt_id = _book(h, _at(day, 11))
    assert "11:00" not in _slots(day)

    r = client.post(f"/api/me/appointments/{appt_id}/cancel", headers=h)
    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["payment_status"], r.json()["state"]) == ("cancelled", "refunded", "cancelled")
    assert "11:00" in _slots(day)  # el horario vuelve a estar libre
    admin = client.get("/api/admin/appointments", headers=ADMIN).json()
    assert next(a for a in admin if a["id"] == appt_id)["payment_status"] == "refunded"


def test_cannot_cancel_someone_elses():
    h, _ = _register()
    appt_id = _book(h, _at(_open_day(3), 11))
    other_h, _ = _register("otro@correo.com")
    assert client.post(f"/api/me/appointments/{appt_id}/cancel", headers=other_h).status_code == 404


def test_cannot_cancel_within_deadline_past_or_cancelled():
    h, cid = _register()
    soon = _insert(cid, local_now().replace(microsecond=0) + timedelta(hours=3))   # dentro de las 24 h
    past = _insert(cid, _at(_open_day(-3), 11), status=models.STATUS_DONE)
    gone = _insert(cid, _at(_open_day(4), 12), status=models.STATUS_CANCELLED)

    r = client.post(f"/api/me/appointments/{soon}/cancel", headers=h)
    assert r.status_code == 409 and "24 h antes" in r.json()["detail"]
    for appt_id in (past, gone):
        r = client.post(f"/api/me/appointments/{appt_id}/cancel", headers=h)
        assert r.status_code == 409 and "cancelada o ya pasó" in r.json()["detail"]


# ---------- Reprogramar ----------
def test_reschedule_to_another_day_keeps_payment_and_frees_old_slot():
    h, _ = _register()
    old_day, new_day = _open_day(3), _open_day(6)
    appt_id = _book(h, _at(old_day, 11))
    db = SessionLocal()
    db.get(models.Appointment, appt_id).reminder_sent = True
    db.commit()
    db.close()

    r = client.post(f"/api/me/appointments/{appt_id}/reschedule", headers=h,
                    json={"start_at": _at(new_day, 15).isoformat()})
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["id"] == appt_id                                  # se mueve la misma cita
    assert a["start_at"].startswith(f"{new_day.isoformat()}T15:00")
    assert a["end_at"].startswith(f"{new_day.isoformat()}T15:30")
    assert (a["payment_status"], a["price_paid_cents"]) == ("paid", 1250)
    assert a["reminder_sent"] is False                         # se volverá a recordar
    assert "11:00" in _slots(old_day)
    assert "15:00" not in _slots(new_day)


def test_reschedule_can_overlap_its_own_current_slot():
    # Tinte de 60 min a las 10:00; moverlo a las 10:30 se solapa con su propio horario actual.
    h, _ = _register()
    day = _open_day(3)
    appt_id = _book(h, _at(day, 10), service="Tinte", minutes=60)
    assert "10:30" not in _slots(day, "Tinte")                                 # sin excluir: ocupado
    assert "10:30" in _slots(day, "Tinte", headers=h, exclude_id=appt_id)      # excluyendo la propia
    r = client.post(f"/api/me/appointments/{appt_id}/reschedule", headers=h,
                    json={"start_at": _at(day, 10, 30).isoformat()})
    assert r.status_code == 200, r.text


def test_exclude_is_ignored_for_other_customers():
    h, _ = _register()
    day = _open_day(3)
    appt_id = _book(h, _at(day, 11))
    other_h, _ = _register("otro@correo.com")
    assert "11:00" not in _slots(day, headers=other_h, exclude_id=appt_id)
    assert "11:00" not in _slots(day, exclude_id=appt_id)                     # sin sesión


def test_reschedule_rejects_taken_same_and_invalid_slots():
    h, _ = _register()
    day = _open_day(3)
    appt_id = _book(h, _at(day, 11))
    other_h, _ = _register("otro@correo.com")
    _book(other_h, _at(day, 14))

    def move(start):
        return client.post(f"/api/me/appointments/{appt_id}/reschedule", headers=h, json={"start_at": start.isoformat()})

    assert move(_at(day, 14)).status_code == 409             # ocupado por otro cliente
    assert move(_at(day, 11)).status_code == 422             # mismo horario
    assert move(_at(day, 21)).status_code == 409             # fuera del horario de atención
    sunday = day + timedelta(days=(6 - day.weekday()) % 7)
    assert move(_at(sunday, 11)).status_code == 409          # día cerrado


def test_reschedule_within_deadline_or_someone_elses():
    h, cid = _register()
    soon = _insert(cid, local_now().replace(microsecond=0) + timedelta(hours=3))
    r = client.post(f"/api/me/appointments/{soon}/reschedule", headers=h,
                    json={"start_at": _at(_open_day(5), 11).isoformat()})
    assert r.status_code == 409 and "reprogramar hasta 24 h antes" in r.json()["detail"]

    other_h, _ = _register("otro@correo.com")
    mine = _book(h, _at(_open_day(3), 11))
    r = client.post(f"/api/me/appointments/{mine}/reschedule", headers=other_h,
                    json={"start_at": _at(_open_day(5), 11).isoformat()})
    assert r.status_code == 404
