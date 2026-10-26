"""Tests de estadísticas reales y previsión (US-03, #20, H-27, H-28) con datos conocidos."""
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
NEXT_4_WEEKS = (TODAY.isoformat(), (TODAY + timedelta(days=27)).isoformat())


def _past_week(i: int) -> date:
    """Lunes de la i-ésima semana completa anterior (1 = la semana pasada)."""
    return CURRENT_WEEK - timedelta(weeks=i)


def _next_open_day() -> date:
    d = TODAY + timedelta(days=1)
    while d.weekday() == 6:
        d += timedelta(days=1)
    return d


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


def _get(start=None, end=None, service_id=None, status=200):
    params = {k: v for k, v in {"start": start, "end": end, "service_id": service_id}.items() if v is not None}
    r = client.get("/api/admin/forecast", headers=ADMIN, params=params)
    assert r.status_code == status, r.text
    return r.json()


def _fc_days(data, wd):
    return [d for d in data["forecast"]["daily"] if date.fromisoformat(d["date"]).weekday() == wd]


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


# ---------- Datos reales (H-28) ----------
def test_real_counts_reconcile_with_reservations_tab():
    # H-28: total = registradas + canceladas, y coincide con /api/admin/stats.
    tue = _past_week(1) + timedelta(days=1)
    _add(tue, 3)                                                       # realizadas
    _add(tue, 1, status=models.STATUS_CANCELLED, start_hour=15)        # cancelada pasada
    _add(_next_open_day(), 2, status=models.STATUS_CONFIRMED)          # reservadas
    _add(_next_open_day(), 1, status=models.STATUS_CANCELLED, start_hour=16)

    k = _get(_past_week(2).isoformat(), max_booking_date().isoformat())["real"]["kpis"]
    stats = client.get("/api/admin/stats", headers=ADMIN).json()
    assert (k["total"], k["registered"], k["done"], k["booked"], k["cancelled"]) == (7, 5, 3, 2, 2)
    assert k["registered"] + k["cancelled"] == k["total"] == stats["total"]
    assert k["cancelled"] == stats["cancelled"]
    assert k["booked"] == stats["upcoming"]
    assert k["cancellation_rate_pct"] == round(2 / 7 * 100, 1)


def test_real_revenue_ticket_and_occupancy():
    tue = _past_week(2) + timedelta(days=1)
    _add(tue, 3, price=1000)
    _add(_next_open_day(), 1, price=1800, status=models.STATUS_PENDING)  # reserva ya pagada
    data = _get(_past_week(2).isoformat(), (_past_week(2) + timedelta(days=6)).isoformat())
    k = data["real"]["kpis"]
    assert (k["revenue_cents"], k["avg_ticket_cents"]) == (3000, 1000)  # la reserva futura está fuera del rango
    # 3 turnos de 30 min en 6 días abiertos de 600 min = 90 / 3600 = 2.5 %
    assert k["occupancy_pct"] == 2.5
    assert data["real"]["basis"] == "done"
    assert data["real"]["weekly"] == [{"week_start": _past_week(2).isoformat(), "done": 3, "booked": 0, "cancelled": 0}]

    both = _get(_past_week(2).isoformat(), max_booking_date().isoformat())["real"]["kpis"]
    assert both["revenue_cents"] == 4800  # cobrado = realizadas + reservadas (prepagadas)


def test_real_basis_uses_bookings_for_future_only_range():
    nxt = _next_open_day()
    _add(nxt, 2, status=models.STATUS_CONFIRMED, start_hour=17)
    real = _get(nxt.isoformat(), nxt.isoformat())["real"]
    assert real["basis"] == "booked"
    assert real["kpis"]["occupancy_pct"] == 10.0
    assert next(h for h in real["by_hour"] if h["hour"] == "17:00")["occupancy_pct"] == 100.0


def test_real_section_never_includes_estimates():
    # Con histórico, la previsión estima citas a futuro, pero los KPIs reales no cambian.
    for i in range(1, 9):
        _add(_past_week(i) + timedelta(days=5), 4)
    data = _get(*NEXT_4_WEEKS)
    assert data["forecast"]["kpis"]["expected"] > 0
    assert data["real"]["kpis"]["registered"] == 0


def test_days_classified_against_business_average():
    # Viernes y sábados 30 %, resto 10 %: con un umbral absoluto todos serían "baja".
    for i in range(1, 9):
        for wd in range(6):
            _add(_past_week(i) + timedelta(days=wd), 6 if wd in (4, 5) else 2)
    real = _get(_past_week(8).isoformat(), (CURRENT_WEEK - timedelta(days=1)).isoformat())["real"]
    levels = {w["weekday"]: w["level"] for w in real["by_weekday"]}
    assert (levels["Vie"], levels["Sáb"]) == ("high", "high")
    assert {levels[d] for d in ("Lun", "Mar", "Mié", "Jue")} == {"low"}
    texts = " ".join(s["text"] for s in real["suggestions"])
    assert "Mayor demanda los viernes y sábados" in texts
    assert "Previsión" not in texts  # las sugerencias reales no mencionan estimaciones


# ---------- Previsión ----------
def test_constant_demand_split_by_weekday():
    # 8 semanas: 4 citas cada sábado y 1 cada lunes -> 5 por semana, sin tendencia.
    for i in range(1, 9):
        _add(_past_week(i) + timedelta(days=5), 4)
        _add(_past_week(i), 1)
    fc = _get(*NEXT_4_WEEKS)["forecast"]
    assert fc["kpis"]["trend_pct_per_week"] == 0.0
    data = {"forecast": fc}
    assert {d["expected"] for d in _fc_days(data, 5)} == {4.0}   # sábados
    assert {d["expected"] for d in _fc_days(data, 0)} == {1.0}   # lunes
    assert {d["expected"] for d in _fc_days(data, 1)} == {0.0}   # martes
    assert {d["occupancy_pct"] for d in _fc_days(data, 5)} == {20.0}  # 4 × 30 min / 600


def test_growing_demand_is_damped():
    # La recta real tiene b = 1 (≈ 22 % del promedio 4.5): se amortigua a ±10 % -> b = 0.45,
    # re-centrada en el promedio: a = 4.5 - 0.45 × 3.5 = 2.925.
    for i in range(1, 9):
        _add(_past_week(i) + timedelta(days=5), 9 - i)
    data = _get(*NEXT_4_WEEKS)
    assert data["forecast"]["kpis"]["trend_pct_per_week"] == 10.0
    for d in _fc_days(data, 5):
        weeks_ahead = (date.fromisoformat(d["date"]) - timedelta(days=5) - CURRENT_WEEK).days // 7
        assert d["expected"] == round(2.925 + 0.45 * (8 + weeks_ahead), 1)


def test_declining_trend_is_damped_and_floored():
    # 8, 7, …, 1 citas por semana: sin amortiguar, la recta llega a 0 en pocas semanas.
    for i in range(1, 9):
        _add(_past_week(i) + timedelta(days=5), i)
    data = _get(TODAY.isoformat(), max_booking_date().isoformat())
    assert data["forecast"]["kpis"]["trend_pct_per_week"] == -10.0
    sats = [d["expected"] for d in _fc_days(data, 5)]
    assert min(sats) == 2.2  # piso: 50 % del promedio semanal (4.5 × 0.5 = 2.25)


def test_forecast_never_below_booked_and_additional_excludes_booked():
    # Servicio sin histórico (modelo = 0) pero con una reserva futura (H-27).
    nxt = _next_open_day()
    _add(nxt, 1, status=models.STATUS_CONFIRMED, service="Tinte")
    fc = _get(nxt.isoformat(), nxt.isoformat(), service_id=_service("Tinte"))["forecast"]
    assert (fc["daily"][0]["expected"], fc["daily"][0]["booked"]) == (1.0, 1)
    assert (fc["kpis"]["expected"], fc["kpis"]["booked"], fc["kpis"]["additional"]) == (1.0, 1, 0.0)
    assert fc["weekly"][0]["additional"] == 0.0


def test_forecast_not_available_for_past_range():
    fc = _get(_past_week(2).isoformat(), (_past_week(2) + timedelta(days=6)).isoformat())["forecast"]
    assert fc["available"] is False and fc["daily"] == []
    assert "termina antes de hoy" in fc["suggestions"][0]["text"]


def test_forecast_suggestions_are_labelled_as_estimates():
    for i in range(1, 9):
        _add(_past_week(i) + timedelta(days=5), 18)  # sábados casi llenos
    texts = [s["text"] for s in _get(*NEXT_4_WEEKS)["forecast"]["suggestions"]]
    assert texts and all(t.startswith("Previsión") for t in texts)
    assert any("sábados estarían casi llenos" in t for t in texts)


# ---------- Rango y filtro por servicio ----------
def test_range_defaults():
    data = _get()
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


def test_service_filter_matches_service_chart():
    # El KPI de registradas con un servicio filtrado debe coincidir con su barra en el gráfico.
    for i in range(1, 9):
        _add(_past_week(i) + timedelta(days=5), 4, service="Corte")
        _add(_past_week(i), 2, service="Tinte", price=1800)
    _add(_next_open_day(), 1, status=models.STATUS_CONFIRMED, service="Tinte")
    tinte = _service("Tinte")
    data = _get(_past_week(8).isoformat(), max_booking_date().isoformat(), service_id=tinte)
    bar = next(s for s in data["real"]["by_service"] if s["service_id"] == tinte)
    assert data["real"]["kpis"]["registered"] == bar["appointments"] == 17  # 2 × 8 + 1 reservada
    assert {s["service"] for s in data["real"]["by_service"]} == {"Corte", "Tinte"}
    assert "«Tinte» se concentra los lunes" in " ".join(s["text"] for s in data["real"]["suggestions"])


def test_revenue_uses_price_paid():
    _add(_past_week(1) + timedelta(days=2), 3, price=1000)
    db = SessionLocal()
    db.query(models.Service).filter_by(name="Corte").first().price_cents = 9999  # cambio posterior
    db.commit()
    db.close()
    real = _get(_past_week(1).isoformat(), (CURRENT_WEEK - timedelta(days=1)).isoformat())["real"]
    assert [(s["service"], s["appointments"], s["revenue_cents"]) for s in real["by_service"]] == [("Corte", 3, 3000)]


def test_cancellation_suggestion():
    tue = _past_week(1) + timedelta(days=1)
    _add(tue, 3)
    _add(tue, 2, status=models.STATUS_CANCELLED, start_hour=15)  # 40 % canceladas
    real = _get(_past_week(1).isoformat(), (CURRENT_WEEK - timedelta(days=1)).isoformat())["real"]
    assert any("se cancelaron" in s["text"] for s in real["suggestions"])


def test_empty_range():
    data = _get(*NEXT_4_WEEKS)
    assert data["real"]["kpis"]["total"] == 0
    assert data["forecast"]["suggestions"] == [
        {"level": "info", "text": "Aún no hay suficiente histórico para generar sugerencias."}]


def test_forecast_requires_admin():
    assert client.get("/api/admin/forecast").status_code == 422  # falta cabecera
    assert client.get("/api/admin/forecast", headers={"X-Admin-Token": "malo"}).status_code == 401
