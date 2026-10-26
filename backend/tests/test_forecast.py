"""Tests de la previsión de demanda (US-03 y #20) con datos conocidos."""
from datetime import date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient

from app import models
from app.availability import max_booking_date
from app.database import SessionLocal
from app.forecast import _linear_fit, _minutes
from app.main import app
from app.utils import add_months, local_now

client = TestClient(app)
ADMIN = {"X-Admin-Token": "test-token"}

TODAY = local_now().date()
CURRENT_WEEK = TODAY - timedelta(days=TODAY.weekday())
NEXT_4_WEEKS = (TODAY, TODAY + timedelta(days=27))


def _past_week(i: int) -> date:
    """Lunes de la i-ésima semana completa anterior (1 = la semana pasada)."""
    return CURRENT_WEEK - timedelta(weeks=i)


def _service(name="Corte"):
    db = SessionLocal()
    svc = db.query(models.Service).filter_by(name=name).first()
    if not svc:
        svc = models.Service(name=name, duration_min=30, price_cents=1800, active=True)
        db.add(svc)
        db.commit()
    sid = svc.id
    db.close()
    return sid


def _add(day: date, n: int, status=models.STATUS_DONE, price=1250, start_hour=10, service="Corte"):
    """n citas de 30 min seguidas desde start_hour."""
    sid = _service(service)
    db = SessionLocal()
    for k in range(n):
        start = datetime.combine(day, time(hour=start_hour)) + timedelta(minutes=30 * k)
        db.add(models.Appointment(
            customer_name="Cliente", customer_phone="+50761234567", service_id=sid,
            start_at=start, end_at=start + timedelta(minutes=30), status=status,
            payment_status=models.PAYMENT_PAID, price_paid_cents=price,
            payment_brand="Visa", payment_last4="4242",
            created_at=start - timedelta(days=1)))  # explícito: evita el default obsoleto (H-21)
    db.commit()
    db.close()


def _forecast(start=None, end=None, service_id=None, status=200):
    params = {k: v for k, v in {"start": start, "end": end, "service_id": service_id}.items() if v is not None}
    r = client.get("/api/admin/forecast", headers=ADMIN, params=params)
    assert r.status_code == status, r.text
    return r.json()


def _days(data, wd, kind=None):
    return [d for d in data["daily"]
            if date.fromisoformat(d["date"]).weekday() == wd and (kind is None or d["kind"] == kind)]


# ---------- Cálculo base ----------
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
    for i in range(1, 9):
        _add(_past_week(i) + timedelta(days=5), 4)
        _add(_past_week(i), 1)

    data = _forecast(*NEXT_4_WEEKS)
    assert data["kpis"]["trend_pct_per_week"] == 0.0
    assert {d["expected"] for d in _days(data, 5)} == {4.0}   # sábados
    assert {d["expected"] for d in _days(data, 0)} == {1.0}   # lunes
    assert {d["expected"] for d in _days(data, 1)} == {0.0}   # martes
    # 4 citas × 30 min sobre 600 min de atención = 20 %
    assert {d["occupancy_pct"] for d in _days(data, 5)} == {20.0}
    assert all(d["kind"] == "forecast" for d in data["daily"])


def test_growing_demand_follows_trend():
    # Semana más antigua: 1 cita el sábado; la más reciente: 8 -> crece 1 por semana.
    for i in range(1, 9):
        _add(_past_week(i) + timedelta(days=5), 9 - i)

    data = _forecast(*NEXT_4_WEEKS)
    # La recta real tiene b = 1 (≈ 22 % del promedio 4.5): se amortigua a ±10 % -> b = 0.45,
    # re-centrada en el promedio: a = 4.5 - 0.45 × 3.5 = 2.925.
    assert data["kpis"]["trend_pct_per_week"] == 10.0
    for d in _days(data, 5):
        weeks_ahead = (date.fromisoformat(d["date"]) - timedelta(days=5) - CURRENT_WEEK).days // 7
        assert d["expected"] == round(2.925 + 0.45 * (8 + weeks_ahead), 1)


def test_declining_trend_is_damped_and_floored():
    # 8, 7, …, 1 citas por semana: sin amortiguar, la recta llega a 0 en pocas semanas.
    for i in range(1, 9):
        _add(_past_week(i) + timedelta(days=5), i)
    data = _forecast(TODAY.isoformat(), max_booking_date().isoformat())
    assert data["kpis"]["trend_pct_per_week"] == -10.0
    sats = [d["expected"] for d in _days(data, 5)]
    assert min(sats) == 2.2  # piso: 50 % del promedio semanal (4.5 × 0.5 = 2.25)
    assert all(x > 0 for x in sats)


def test_forecast_never_below_booked():
    # Servicio sin histórico (previsión del modelo = 0) pero con una reserva futura.
    nxt = TODAY + timedelta(days=1)
    while nxt.weekday() == 6:
        nxt += timedelta(days=1)
    _add(nxt, 1, status=models.STATUS_CONFIRMED, service="Tinte")
    data = _forecast(nxt.isoformat(), nxt.isoformat(), service_id=_service("Tinte"))
    day = data["daily"][0]
    assert (day["expected"], day["booked"]) == (1.0, 1)
    assert data["kpis"]["expected_appointments"] == 1.0
    assert data["kpis"]["booked_appointments"] == 1


# ---------- Rango de fechas (#20) ----------
def test_past_range_shows_real_data_and_kpis():
    tue = _past_week(2) + timedelta(days=1)
    _add(tue, 3, price=1000)
    _add(tue, 1, status=models.STATUS_CANCELLED, start_hour=15)
    data = _forecast(_past_week(2).isoformat(), (_past_week(2) + timedelta(days=6)).isoformat())

    day = next(d for d in data["daily"] if d["date"] == tue.isoformat())
    assert (day["kind"], day["real"], day["expected"], day["occupancy_pct"]) == ("real", 3, None, 15.0)
    k = data["kpis"]
    assert (k["real_appointments"], k["expected_appointments"], k["booked_appointments"]) == (3, 0, 0)
    assert (k["revenue_cents"], k["avg_ticket_cents"]) == (3000, 1000)
    assert k["cancellation_rate_pct"] == 25.0  # 1 de 4
    assert data["weekly"] == [{"week_start": _past_week(2).isoformat(), "real": 3, "expected": 0.0, "booked": 0}]


def test_range_mixes_real_past_and_forecast_future():
    data = _forecast((TODAY - timedelta(days=14)).isoformat(), (TODAY + timedelta(days=14)).isoformat())
    kinds = {d["kind"] for d in data["daily"]}
    assert kinds == {"real", "forecast"}
    assert all(d["kind"] == ("real" if date.fromisoformat(d["date"]) < TODAY else "forecast")
               for d in data["daily"])


def test_range_defaults():
    data = _forecast()
    assert data["start"] == (TODAY - timedelta(weeks=4)).isoformat()
    assert data["end"] == (add_months(TODAY, 1) - timedelta(days=1)).isoformat()
    assert data["service"] is None


@pytest.mark.parametrize(
    "params, status",
    [
        ({"start": "2026-11-10", "end": "2026-11-01"}, 422),                  # hasta < desde
        ({"end": (max_booking_date() + timedelta(days=1)).isoformat()}, 422),  # pasa el límite de reservas
        ({"start": "2020-01-01", "end": TODAY.isoformat()}, 422),             # más de un año
        ({"start": "no-es-fecha"}, 422),
        ({"service_id": 999}, 404),
    ],
)
def test_range_validation(params, status):
    assert client.get("/api/admin/forecast", headers=ADMIN, params=params).status_code == status


def test_hour_basis_uses_bookings_for_future_only_range():
    nxt = TODAY + timedelta(days=1)
    while nxt.weekday() == 6:
        nxt += timedelta(days=1)
    _add(nxt, 2, status=models.STATUS_CONFIRMED, start_hour=17)
    data = _forecast(nxt.isoformat(), nxt.isoformat())
    assert data["hour_basis"] == "booked"
    assert next(h for h in data["by_hour"] if h["hour"] == "17:00")["occupancy_pct"] == 100.0
    day = data["daily"][0]
    assert (day["booked"], day["booked_occupancy_pct"]) == (2, 10.0)
    assert data["kpis"]["booked_appointments"] == 2


# ---------- Filtro por servicio (#20) ----------
def test_service_filter_applies_to_everything_but_service_list():
    for i in range(1, 9):
        _add(_past_week(i) + timedelta(days=5), 4, service="Corte")   # sábados
        _add(_past_week(i), 2, service="Tinte", price=1800)          # lunes
    tinte = _service("Tinte")

    data = _forecast(*NEXT_4_WEEKS, service_id=tinte)
    assert data["service"] == {"id": tinte, "name": "Tinte"}
    assert {d["expected"] for d in _days(data, 0)} == {2.0}   # lunes: solo Tinte
    assert {d["expected"] for d in _days(data, 5)} == {0.0}   # sábados: Corte no cuenta
    texts = " ".join(s["text"] for s in data["suggestions"])
    assert "«Tinte» se concentra los lunes" in texts

    # la lista de servicios no se filtra: sirve para elegir otro
    past = _forecast(_past_week(8).isoformat(), (CURRENT_WEEK - timedelta(days=1)).isoformat(), service_id=tinte)
    assert {s["service"] for s in past["by_service"]} == {"Corte", "Tinte"}
    assert past["kpis"]["real_appointments"] == 16  # solo Tinte: 2 × 8 semanas


def test_revenue_uses_price_paid():
    _add(_past_week(1) + timedelta(days=2), 3, price=1000)
    db = SessionLocal()
    db.query(models.Service).filter_by(name="Corte").first().price_cents = 9999  # cambio posterior
    db.commit()
    db.close()
    data = _forecast(_past_week(1).isoformat(), (CURRENT_WEEK - timedelta(days=1)).isoformat())
    assert [(s["service"], s["appointments"], s["revenue_cents"]) for s in data["by_service"]] == [("Corte", 3, 3000)]


# ---------- Sugerencias ----------
def test_empty_history():
    data = _forecast(*NEXT_4_WEEKS)
    assert data["kpis"]["expected_appointments"] == 0
    assert data["suggestions"] == [
        {"level": "info", "text": "Aún no hay suficiente histórico para generar sugerencias."}]


def test_suggestions_full_day_and_low_demand():
    # Sábados casi llenos (18 × 30 min = 90 %), resto vacío.
    for i in range(1, 9):
        _add(_past_week(i) + timedelta(days=5), 18)
    texts = [s["text"] for s in _forecast(*NEXT_4_WEEKS)["suggestions"]]
    assert any("sábados están casi llenos" in t for t in texts)
    assert any("Menor demanda" in t and "lunes" in t for t in texts)
    assert any("capacidad libre" in t for t in texts)  # promedio (15 %) bajo el 40 %


def test_days_classified_against_business_average():
    # Negocio moderado: viernes y sábados 30 %, resto 10 %. Con un umbral absoluto de 40 %
    # todos serían "baja demanda"; contra el promedio (≈ 16.7 %) se distinguen.
    for i in range(1, 9):
        for wd in range(6):
            _add(_past_week(i) + timedelta(days=wd), 6 if wd in (4, 5) else 2)
    data = _forecast(*NEXT_4_WEEKS)
    levels = {w["weekday"]: w["level"] for w in data["by_weekday"]}
    assert (levels["Vie"], levels["Sáb"]) == ("high", "high")
    assert {levels[d] for d in ("Lun", "Mar", "Mié", "Jue")} == {"low"}
    texts = " ".join(s["text"] for s in data["suggestions"])
    assert "Mayor demanda los viernes y sábados" in texts
    assert "casi llenos" not in texts


def test_cancellation_suggestion():
    tue = _past_week(1) + timedelta(days=1)
    _add(tue, 3)
    _add(tue, 2, status=models.STATUS_CANCELLED, start_hour=15)  # 40 % canceladas
    data = _forecast(_past_week(1).isoformat(), (CURRENT_WEEK - timedelta(days=1)).isoformat())
    assert any("se cancelaron" in s["text"] for s in data["suggestions"])


def test_forecast_requires_admin():
    assert client.get("/api/admin/forecast").status_code == 422  # falta cabecera
    assert client.get("/api/admin/forecast", headers={"X-Admin-Token": "malo"}).status_code == 401
