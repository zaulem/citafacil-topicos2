"""Tests de la previsión de demanda (US-03) con datos conocidos."""
from datetime import date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient

from app import models
from app.database import SessionLocal
from app.forecast import _linear_fit, _minutes
from app.main import app
from app.utils import add_months, local_now

client = TestClient(app)
ADMIN = {"X-Admin-Token": "test-token"}

TODAY = local_now().date()
CURRENT_WEEK = TODAY - timedelta(days=TODAY.weekday())


def _past_week(i: int) -> date:
    """Lunes de la i-ésima semana completa anterior (1 = la semana pasada)."""
    return CURRENT_WEEK - timedelta(weeks=i)


def _add(db, day: date, n: int, status=models.STATUS_DONE, price=1250, start_hour=10):
    """n citas de 30 min seguidas desde start_hour."""
    sid = db.query(models.Service).first().id
    for k in range(n):
        start = datetime.combine(day, time(hour=start_hour)) + timedelta(minutes=30 * k)
        db.add(models.Appointment(
            customer_name="Cliente", customer_phone="+50761234567", service_id=sid,
            start_at=start, end_at=start + timedelta(minutes=30), status=status,
            payment_status=models.PAYMENT_PAID, price_paid_cents=price,
            payment_brand="Visa", payment_last4="4242",
            created_at=start - timedelta(days=1)))  # explícito: evita el default obsoleto (H-21)
    db.commit()


def _forecast(months=1):
    r = client.get(f"/api/admin/forecast?months={months}", headers=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()


def _days_by_weekday(data, wd):
    return [d for d in data["forecast_daily"] if date.fromisoformat(d["date"]).weekday() == wd]


def test_occupancy_counts_blocked_slots():
    # Una cita de 20 min bloquea un turno completo de 30 min; una de 45, dos turnos.
    start = datetime(2026, 1, 5, 10, 0)
    for duration, blocked in [(20, 30), (30, 30), (45, 60), (60, 60)]:
        appt = models.Appointment(start_at=start, end_at=start + timedelta(minutes=duration))
        assert _minutes(appt) == blocked


def test_linear_fit():
    assert _linear_fit([5, 5, 5, 5]) == (5.0, 0.0)
    a, b = _linear_fit([1, 2, 3, 4, 5, 6, 7, 8])
    assert (round(a, 6), round(b, 6)) == (1.0, 1.0)
    assert _linear_fit([]) == (0.0, 0.0)


def test_constant_demand_split_by_weekday():
    # 8 semanas: 4 citas cada sábado y 1 cada lunes -> 5 por semana, sin tendencia.
    db = SessionLocal()
    for i in range(1, 9):
        _add(db, _past_week(i) + timedelta(days=5), 4)
        _add(db, _past_week(i), 1)
    db.close()

    data = _forecast()
    assert data["kpis"]["trend_pct_per_week"] == 0.0
    # semana completa, incluida la actual aunque ya hayan pasado días (sin caída falsa)
    assert {w["expected"] for w in data["forecast_weekly"]} == {5.0}
    assert data["forecast_weekly"][0]["week_start"] == CURRENT_WEEK.isoformat()
    assert {d["expected"] for d in _days_by_weekday(data, 5)} == {4.0}   # sábados
    assert {d["expected"] for d in _days_by_weekday(data, 0)} == {1.0}   # lunes
    assert {d["expected"] for d in _days_by_weekday(data, 1)} == {0.0}   # martes
    # 4 citas × 30 min sobre 600 min de atención = 20 %
    assert {d["expected_occupancy_pct"] for d in _days_by_weekday(data, 5)} == {20.0}
    sat = next(w for w in data["by_weekday"] if w["weekday"] == "Sáb")
    assert (sat["avg_appointments"], sat["historical_occupancy_pct"]) == (4.0, 20.0)


def test_growing_demand_follows_trend():
    # Semana más antigua: 1 cita el sábado; la más reciente: 8 -> crece 1 por semana.
    db = SessionLocal()
    for i in range(1, 9):
        _add(db, _past_week(i) + timedelta(days=5), 9 - i)
    db.close()

    data = _forecast()
    assert data["kpis"]["trend_pct_per_week"] == round(1 / 4.5 * 100, 1)
    for d in _days_by_weekday(data, 5):
        weeks_ahead = (date.fromisoformat(d["date"]) - timedelta(days=5) - CURRENT_WEEK).days // 7
        assert d["expected"] == 1 + 1 * (8 + weeks_ahead)  # recta a + b·x con a = 1, b = 1


def test_cancelled_appointments_are_not_demand():
    db = SessionLocal()
    for i in range(1, 9):
        _add(db, _past_week(i) + timedelta(days=5), 4)
        _add(db, _past_week(i) + timedelta(days=1), 6, status=models.STATUS_CANCELLED)
    db.close()
    data = _forecast()
    assert {d["expected"] for d in _days_by_weekday(data, 1)} == {0.0}
    assert sum(w["appointments"] for w in data["history"]) == 32


def test_revenue_uses_price_paid():
    db = SessionLocal()
    _add(db, _past_week(1) + timedelta(days=2), 3, price=1000)
    svc = db.query(models.Service).first()
    svc.price_cents = 9999  # cambio de precio posterior
    db.commit()
    db.close()
    data = _forecast()
    assert data["by_service"] == [{"service": "Corte", "appointments": 3, "revenue_cents": 3000}]
    assert sum(w["revenue_cents"] for w in data["history"]) == 3000


def test_horizon_closed_days_and_booked():
    nxt = TODAY + timedelta(days=1)
    while nxt.weekday() == 6:
        nxt += timedelta(days=1)
    db = SessionLocal()
    _add(db, nxt, 2, status=models.STATUS_CONFIRMED)
    db.close()

    data = _forecast(months=2)
    assert data["horizon_end"] == (add_months(TODAY, 2) - timedelta(days=1)).isoformat()
    assert not _days_by_weekday(data, 6)  # domingo cerrado
    day = next(d for d in data["forecast_daily"] if d["date"] == nxt.isoformat())
    assert (day["booked"], day["booked_occupancy_pct"]) == (2, 10.0)
    assert data["kpis"]["booked_appointments"] == 2


def test_empty_history():
    data = _forecast()
    assert data["kpis"]["expected_appointments"] == 0
    assert data["suggestions"] == [
        {"level": "info", "text": "Aún no hay suficiente histórico para generar sugerencias."}]


def test_suggestions_for_high_and_low_demand():
    # Sábados casi llenos (18 × 30 min = 90 %), resto vacío.
    db = SessionLocal()
    for i in range(1, 9):
        _add(db, _past_week(i) + timedelta(days=5), 18)
    db.close()
    texts = [s["text"] for s in _forecast()["suggestions"]]
    assert any("Alta demanda" in t and "sábados" in t for t in texts)
    assert any("Baja demanda" in t and "lunes" in t for t in texts)
    assert any("«Corte» genera el 100 %" in t for t in texts)


def test_forecast_requires_admin():
    assert client.get("/api/admin/forecast").status_code == 422  # falta cabecera
    assert client.get("/api/admin/forecast", headers={"X-Admin-Token": "malo"}).status_code == 401


@pytest.mark.parametrize("months", [0, 4])
def test_forecast_months_range(months):
    assert client.get(f"/api/admin/forecast?months={months}", headers=ADMIN).status_code == 422
