"""Previsión de demanda (US-03).

Método (explicable sin estadística avanzada):
1. Se toman las últimas BASELINE_WEEKS semanas completas (sin la semana actual).
2. Tendencia: recta de mínimos cuadrados sobre el total de citas de cada semana.
   La semana futura x se estima como `a + b·x` (la semana actual es x = BASELINE_WEEKS).
3. Ese total semanal se reparte entre los días según el peso histórico de cada día
   de la semana (p. ej., si los sábados concentran el 25 % de las citas, reciben el 25 %).
4. Ocupación = tiempo bloqueado en turnos (reservado o previsto) / tiempo de atención
   del día. Los turnos son el "inventario" de la barbería: una cita de 20 min bloquea
   un turno de 30 min completo.

Las citas canceladas no cuentan como demanda. Los ingresos usan `price_paid_cents`
(lo que se cobró), no el precio actual del servicio (H-15).
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from . import models
from .config import settings
from .utils import add_months, local_now

BASELINE_WEEKS = 8      # semanas completas usadas para el promedio y la tendencia
HISTORY_WEEKS = 26      # semanas que se muestran en el histórico (~6 meses)
HIGH_OCCUPANCY = 85.0   # % desde el que se sugiere subir precio o ampliar horario
LOW_OCCUPANCY = 40.0    # % bajo el que se sugiere una promoción
LOW_HOUR_OCCUPANCY = 25.0
TREND_ALERT = 3.0       # % de variación semanal que merece una sugerencia

WEEKDAY_SHORT = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
WEEKDAY_PLURAL = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábados", "domingos"]


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _linear_fit(ys: list[float]) -> tuple[float, float]:
    """Recta y = a + b·x por mínimos cuadrados, con x = 0..n-1."""
    n = len(ys)
    if n == 0:
        return 0.0, 0.0
    if n == 1:
        return float(ys[0]), 0.0
    mean_x, mean_y = (n - 1) / 2, sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in range(n))
    b = sum((x - mean_x) * (y - mean_y) for x, y in enumerate(ys)) / sxx
    return mean_y - b * mean_x, b


def _minutes(a: models.Appointment) -> float:
    """Minutos que la cita bloquea en la grilla de turnos: un servicio de 20 min ocupa
    un turno completo de 30 min, porque nadie más puede usar esos 10 min."""
    step = settings.slot_interval_minutes
    duration = (a.end_at - a.start_at).total_seconds() / 60
    return math.ceil(duration / step) * step


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]


def build_forecast(db: Session, months: int) -> dict:
    today = local_now().date()
    current_week = _week_start(today)
    hist_start = current_week - timedelta(weeks=HISTORY_WEEKS)
    base_start = current_week - timedelta(weeks=BASELINE_WEEKS)
    horizon_end = add_months(today, months)  # exclusivo
    open_days = [w for w in range(7) if w not in settings.closed_weekdays_set]
    open_min = (settings.close_hour - settings.open_hour) * 60

    appts = (
        db.query(models.Appointment)
        .filter(
            models.Appointment.status != models.STATUS_CANCELLED,
            models.Appointment.start_at >= datetime.combine(hist_start, time.min),
            models.Appointment.start_at < datetime.combine(horizon_end, time.min),
        )
        .all()
    )
    past = [a for a in appts if a.start_at.date() < current_week]
    baseline = [a for a in past if a.start_at.date() >= base_start]
    future = [a for a in appts if a.start_at.date() >= today]

    # ---------- Histórico semanal ----------
    weekly = {hist_start + timedelta(weeks=i): [0, 0] for i in range(HISTORY_WEEKS)}
    for a in past:
        w = weekly[_week_start(a.start_at.date())]
        w[0] += 1
        w[1] += a.price_paid_cents or 0
    history = [
        {"week_start": ws.isoformat(), "appointments": n, "revenue_cents": rev}
        for ws, (n, rev) in sorted(weekly.items())
    ]

    # ---------- Modelo: tendencia + peso de cada día ----------
    totals = [weekly[base_start + timedelta(weeks=i)][0] for i in range(BASELINE_WEEKS)]
    a_fit, b_fit = _linear_fit(totals)
    mean_week = sum(totals) / BASELINE_WEEKS
    trend_pct = (b_fit / mean_week * 100) if mean_week else 0.0

    by_wd_count: dict[int, int] = defaultdict(int)
    by_wd_minutes: dict[int, float] = defaultdict(float)
    for a in baseline:
        by_wd_count[a.start_at.weekday()] += 1
        by_wd_minutes[a.start_at.weekday()] += _minutes(a)
    total_base = len(baseline)
    avg_duration = (sum(_minutes(a) for a in baseline) / total_base) if total_base else 30.0
    paid = [a.price_paid_cents for a in baseline if a.price_paid_cents is not None]
    avg_ticket = (sum(paid) / len(paid)) if paid else 0.0

    # ---------- Previsión diaria ----------
    booked_n: dict[date, int] = defaultdict(int)
    booked_min: dict[date, float] = defaultdict(float)
    for a in future:
        booked_n[a.start_at.date()] += 1
        booked_min[a.start_at.date()] += _minutes(a)

    days = []
    d = today
    while d < horizon_end:
        wd = d.weekday()
        if wd in open_days:
            x = BASELINE_WEEKS + (_week_start(d) - current_week).days // 7
            week_total = max(0.0, a_fit + b_fit * x)
            expected = week_total * by_wd_count[wd] / total_base if total_base else 0.0
            days.append({
                "date": d.isoformat(),
                "expected": round(expected, 1),
                "booked": booked_n[d],
                "expected_occupancy_pct": round(min(100.0, expected * avg_duration / open_min * 100), 1),
                "booked_occupancy_pct": round(min(100.0, booked_min[d] / open_min * 100), 1),
            })
        d += timedelta(days=1)

    # Por semana se usa el total del modelo para la semana completa (a + b·x): si se
    # sumaran solo los días desde hoy, la semana actual aparecería con una caída falsa.
    weekly_booked: dict[date, int] = defaultdict(int)
    for day in days:
        weekly_booked[_week_start(date.fromisoformat(day["date"]))] += day["booked"]
    forecast_weekly = [
        {
            "week_start": ws.isoformat(),
            "expected": round(max(0.0, a_fit + b_fit * (BASELINE_WEEKS + (ws - current_week).days // 7)), 1)
            if total_base else 0.0,
            "booked": n,
        }
        for ws, n in sorted(weekly_booked.items())
    ]

    # ---------- Ocupación por día de la semana y por hora ----------
    by_weekday = []
    for wd in open_days:
        fc = [x["expected_occupancy_pct"] for x in days if date.fromisoformat(x["date"]).weekday() == wd]
        by_weekday.append({
            "weekday": WEEKDAY_SHORT[wd],
            "avg_appointments": round(by_wd_count[wd] / BASELINE_WEEKS, 1),
            "historical_occupancy_pct": round(by_wd_minutes[wd] / (BASELINE_WEEKS * open_min) * 100, 1),
            "expected_occupancy_pct": round(sum(fc) / len(fc), 1) if fc else 0.0,
        })

    open_day_count = BASELINE_WEEKS * len(open_days)
    hour_minutes: dict[int, float] = defaultdict(float)
    for a in baseline:
        for h in range(settings.open_hour, settings.close_hour):
            h_start = datetime.combine(a.start_at.date(), time(hour=h))
            blocked_end = a.start_at + timedelta(minutes=_minutes(a))
            overlap = (min(blocked_end, h_start + timedelta(hours=1)) - max(a.start_at, h_start)).total_seconds()
            if overlap > 0:
                hour_minutes[h] += overlap / 60
    by_hour = [
        {"hour": f"{h:02d}:00", "occupancy_pct": round(hour_minutes[h] / (60 * open_day_count) * 100, 1)}
        for h in range(settings.open_hour, settings.close_hour)
    ]

    svc: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for a in past:
        s = svc[a.service.name if a.service else f"#{a.service_id}"]
        s[0] += 1
        s[1] += a.price_paid_cents or 0
    by_service = sorted(
        ({"service": name, "appointments": n, "revenue_cents": rev} for name, (n, rev) in svc.items()),
        key=lambda x: x["revenue_cents"], reverse=True,
    )

    # ---------- KPIs ----------
    expected_total = sum(x["expected"] for x in days)
    kpis = {
        "expected_appointments": round(expected_total, 1),
        "booked_appointments": sum(x["booked"] for x in days),
        "expected_revenue_cents": round(expected_total * avg_ticket),
        "expected_occupancy_pct": round(sum(x["expected_occupancy_pct"] for x in days) / len(days), 1) if days else 0.0,
        "trend_pct_per_week": round(trend_pct, 1),
    }

    return {
        "months": months,
        "today": today.isoformat(),
        "horizon_end": (horizon_end - timedelta(days=1)).isoformat(),
        "kpis": kpis,
        "history": history,
        "forecast_weekly": forecast_weekly,
        "forecast_daily": days,
        "by_weekday": by_weekday,
        "by_hour": by_hour,
        "by_service": by_service,
        "suggestions": _suggestions(total_base, by_weekday, by_hour, by_service, trend_pct),
    }


def _suggestions(total_base, by_weekday, by_hour, by_service, trend_pct) -> list[dict]:
    """Reglas simples que traducen los datos en acciones de precio e inventario."""
    if not total_base:
        return [{"level": "info", "text": "Aún no hay suficiente histórico para generar sugerencias."}]
    out = []
    full_name = {s: p for s, p in zip(WEEKDAY_SHORT, WEEKDAY_PLURAL)}

    high = [w for w in by_weekday if w["expected_occupancy_pct"] >= HIGH_OCCUPANCY]
    if high:
        pct = round(sum(w["expected_occupancy_pct"] for w in high) / len(high))
        out.append({"level": "high", "text": (
            f"Alta demanda prevista los {_join([full_name[w['weekday']] for w in high])} (≈ {pct} % de ocupación): "
            "considera subir el precio esos días o ampliar el horario de atención.")})
    low = [w for w in by_weekday if w["expected_occupancy_pct"] <= LOW_OCCUPANCY]
    if low:
        pct = round(sum(w["expected_occupancy_pct"] for w in low) / len(low))
        out.append({"level": "low", "text": (
            f"Baja demanda prevista los {_join([full_name[w['weekday']] for w in low])} (≈ {pct} % de ocupación): "
            "considera una promoción o descuento para esos días.")})

    busy = [h["hour"] for h in by_hour if h["occupancy_pct"] >= HIGH_OCCUPANCY]
    if busy:
        out.append({"level": "high", "text": (
            f"Las franjas de las {_join(busy)} suelen estar casi llenas: son candidatas a precio de hora punta.")})
    quiet = [h["hour"] for h in by_hour if h["occupancy_pct"] <= LOW_HOUR_OCCUPANCY]
    if quiet:
        out.append({"level": "low", "text": (
            f"Las franjas de las {_join(quiet)} tienen poca ocupación: ofrece descuentos en esos horarios.")})

    if trend_pct >= TREND_ALERT:
        out.append({"level": "high", "text": (
            f"La demanda crece ≈ {trend_pct:.1f} % por semana: revisa si la capacidad actual alcanzará.")})
    elif trend_pct <= -TREND_ALERT:
        out.append({"level": "low", "text": (
            f"La demanda cae ≈ {abs(trend_pct):.1f} % por semana: considera campañas para recuperar clientes.")})

    revenue = sum(s["revenue_cents"] for s in by_service)
    if revenue and by_service:
        top = by_service[0]
        share = round(top["revenue_cents"] / revenue * 100)
        out.append({"level": "info", "text": (
            f"«{top['service']}» genera el {share} % de los ingresos: prioriza su disponibilidad.")})
    return out
