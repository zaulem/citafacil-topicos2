"""Estadísticas reales y previsión de demanda (US-03, #20, H-27/H-28).

La respuesta tiene DOS secciones que nunca se mezclan:

- `real`: solo citas que existen en la BD dentro del rango (realizadas, reservadas y
  canceladas). Cuadra con la pestaña Reservas: registradas + canceladas = total.
- `forecast`: estimación para los días desde hoy hasta el fin del rango. El panel la
  muestra solo al activar "Mostrar previsión", con un estilo distinto.

Método de la previsión (explicable sin estadística avanzada):
1. Modelo: las últimas BASELINE_WEEKS semanas completas antes de hoy, SIEMPRE las
   mismas sin importar el rango (si no, un rango solo futuro dejaría al modelo sin datos).
2. Tendencia: recta de mínimos cuadrados sobre el total de citas de cada semana,
   AMORTIGUADA: la pendiente se limita a ±TREND_CAP del promedio por semana y la
   previsión no baja de TREND_FLOOR del promedio (con pocos datos, un mes flojo no
   debe proyectar la demanda a cero). La semana futura x se estima como `a + b·x`
   (la semana actual es x = BASELINE_WEEKS).
3. Ese total semanal se reparte entre los días según el peso histórico de cada día
   de la semana. Un día nunca se prevé por debajo de lo que ya tiene reservado.

Ocupación = tiempo bloqueado en turnos / tiempo de atención. Los turnos son el
"inventario" de la barbería: una cita de 20 min bloquea un turno de 30 min completo.
Los ingresos usan `price_paid_cents` (lo cobrado), no el precio actual (H-15).
Con un servicio filtrado, todo (modelo incluido) se calcula solo con ese servicio.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from . import models
from .availability import max_booking_date
from .config import settings
from .utils import local_now

BASELINE_WEEKS = 8      # semanas completas usadas para el promedio y la tendencia
HIGH_OCCUPANCY = 85.0   # % absoluto: día u hora casi llenos
LOW_OCCUPANCY = 40.0    # % de ocupación promedio bajo el que hay capacidad libre para captar clientes
# Días y horas se clasifican contra el promedio del propio negocio: un umbral absoluto
# marcaría "baja demanda" todos los días en un negocio de ocupación moderada.
REL_HIGH = 1.25         # ≥ 125 % del promedio -> mayor demanda
REL_LOW = 0.75          # ≤ 75 % del promedio  -> menor demanda
TREND_ALERT = 3.0       # % de variación semanal que merece una sugerencia
TREND_CAP = 0.10        # la tendencia usada se limita a ±10 % del promedio semanal por semana
TREND_FLOOR = 0.5       # la previsión semanal no baja del 50 % del promedio de las 8 semanas
CANCEL_ALERT = 15.0     # % de cancelaciones que merece una sugerencia

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


def _pct(part: float, whole: float) -> float:
    return round(min(100.0, part / whole * 100), 1) if whole else 0.0


def _classify(items: list[dict]) -> float:
    """Agrega `level` (high | low | normal) a cada item según su `occupancy_pct` comparada
    con el promedio de todos; devuelve ese promedio."""
    values = [x["occupancy_pct"] for x in items if x["occupancy_pct"] is not None]
    avg = sum(values) / len(values) if values else 0.0
    for x in items:
        v = x["occupancy_pct"]
        if v is not None and (v >= HIGH_OCCUPANCY or (avg and v >= avg * REL_HIGH)):
            x["level"] = "high"
        elif v is not None and avg and v <= avg * REL_LOW:
            x["level"] = "low"
        else:
            x["level"] = "normal"
    return avg


def _days_between(start: date, end: date, open_days: list[int]) -> list[date]:
    out, d = [], start
    while d <= end:
        if d.weekday() in open_days:
            out.append(d)
        d += timedelta(days=1)
    return out


def build_forecast(db: Session, start: date, end: date, service: Optional[models.Service] = None) -> dict:
    today = local_now().date()
    current_week = _week_start(today)
    base_start = current_week - timedelta(weeks=BASELINE_WEEKS)
    open_days = [w for w in range(7) if w not in settings.closed_weekdays_set]
    open_min = (settings.close_hour - settings.open_hour) * 60

    def query(service_filter: bool):
        q = db.query(models.Appointment).filter(
            models.Appointment.start_at >= datetime.combine(min(start, base_start), time.min),
            models.Appointment.start_at < datetime.combine(max(end, today) + timedelta(days=1), time.min),
        )
        if service_filter and service:
            q = q.filter(models.Appointment.service_id == service.id)
        return q.all()

    rows = query(service_filter=True)
    in_range = [a for a in rows if start <= a.start_at.date() <= end]
    registered = [a for a in in_range if a.status != models.STATUS_CANCELLED]
    # Realizada: el admin la marcó así o ya pasó su hora (H-35, misma regla que Mis reservas
    # y que "Próximas" en la pestaña Reservas).
    now = local_now()
    done = [a for a in registered if models.is_completed(a, now)]
    booked = [a for a in registered if not models.is_completed(a, now)]
    cancelled = [a for a in in_range if a.status == models.STATUS_CANCELLED]
    # Para la ocupación y la previsión cuenta el día de la cita, no su estado: una cita
    # de mañana marcada Realizada igual ocupa ese turno.
    past = [a for a in registered if a.start_at.date() < today]
    future = [a for a in registered if a.start_at.date() >= today]

    real = _real_section(db, start, end, today, now, open_days, open_min, in_range, registered, done, booked,
                         cancelled, past, future, query, service)
    forecast = _forecast_section(start, end, today, current_week, base_start, open_days, open_min,
                                 rows, future, service)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "today": today.isoformat(),
        "max_date": max_booking_date().isoformat(),
        "service": {"id": service.id, "name": service.name} if service else None,
        "real": real,
        "forecast": forecast,
    }


# ---------- Sección REAL: solo citas que existen ----------
def _real_section(db, start, end, today, now, open_days, open_min, in_range, registered, done, booked,
                  cancelled, past, future, query, service) -> dict:
    revenue = sum(a.price_paid_cents or 0 for a in registered)

    # Ocupación: con días pasados en el rango se mide lo realizado; si el rango es solo
    # futuro, lo ya reservado. Así no se diluye con días futuros aún sin reservas.
    basis = "done" if any(d < today for d in _days_between(start, end, open_days)) else "booked"
    basis_days = [d for d in _days_between(start, end, open_days) if (d < today) == (basis == "done")]
    basis_appts = past if basis == "done" else future

    by_wd_min: dict[int, float] = defaultdict(float)
    hour_min: dict[int, float] = defaultdict(float)
    for a in basis_appts:
        by_wd_min[a.start_at.weekday()] += _minutes(a)
        blocked_end = a.start_at + timedelta(minutes=_minutes(a))
        for h in range(settings.open_hour, settings.close_hour):
            h_start = datetime.combine(a.start_at.date(), time(hour=h))
            overlap = (min(blocked_end, h_start + timedelta(hours=1)) - max(a.start_at, h_start)).total_seconds()
            if overlap > 0:
                hour_min[h] += overlap / 60

    by_weekday = []
    for wd in open_days:
        n_days = sum(1 for d in basis_days if d.weekday() == wd)
        by_weekday.append({"weekday": WEEKDAY_SHORT[wd],
                           "occupancy_pct": _pct(by_wd_min[wd], n_days * open_min) if n_days else None})
    weekday_avg = _classify(by_weekday)
    by_hour = [{"hour": f"{h:02d}:00", "occupancy_pct": _pct(hour_min[h], 60 * len(basis_days))}
               for h in range(settings.open_hour, settings.close_hour)]
    hour_avg = _classify(by_hour)

    weekly: dict[date, dict] = {}
    ws = _week_start(start)
    while ws <= end:
        weekly[ws] = {"week_start": ws.isoformat(), "done": 0, "booked": 0, "cancelled": 0}
        ws += timedelta(weeks=1)
    for a in in_range:
        w = weekly[_week_start(a.start_at.date())]
        if a.status == models.STATUS_CANCELLED:
            w["cancelled"] += 1
        else:
            w["done" if models.is_completed(a, now) else "booked"] += 1

    # Servicios: siempre todos (sin el filtro de servicio), para poder elegir uno.
    svc: dict[int, dict] = {}
    for a in query(service_filter=False):
        if not (start <= a.start_at.date() <= end) or a.status == models.STATUS_CANCELLED:
            continue
        s = svc.setdefault(a.service_id, {"service_id": a.service_id,
                                          "service": a.service.name if a.service else f"#{a.service_id}",
                                          "appointments": 0, "revenue_cents": 0})
        s["appointments"] += 1
        s["revenue_cents"] += a.price_paid_cents or 0
    by_service = sorted(svc.values(), key=lambda x: x["revenue_cents"], reverse=True)

    total = len(in_range)
    cancel_pct = len(cancelled) / total * 100 if total else 0.0
    kpis = {
        "total": total,
        "registered": len(registered),
        "done": len(done),
        "booked": len(booked),
        "cancelled": len(cancelled),
        "cancellation_rate_pct": round(cancel_pct, 1),
        "revenue_cents": revenue,
        "avg_ticket_cents": round(revenue / len(registered)) if registered else 0,
        "occupancy_pct": _pct(sum(_minutes(a) for a in basis_appts), len(basis_days) * open_min),
    }
    if service:
        suggestions = _real_service_suggestions(service.name, registered, cancel_pct, by_service, service.id)
    else:
        suggestions = _real_suggestions(registered, by_weekday, weekday_avg, by_hour, hour_avg,
                                        kpis["occupancy_pct"], by_service, cancel_pct)
    return {
        "basis": basis,
        "kpis": kpis,
        "weekly": [weekly[k] for k in sorted(weekly)],
        "by_weekday": by_weekday,
        "by_hour": by_hour,
        "by_service": by_service,
        "suggestions": suggestions,
    }


# ---------- Sección PREVISIÓN: estimación desde hoy hasta el fin del rango ----------
def _forecast_section(start, end, today, current_week, base_start, open_days, open_min, rows,
                      booked, service) -> dict:
    active = [a for a in rows if a.status != models.STATUS_CANCELLED]
    baseline = [a for a in active if base_start <= a.start_at.date() < current_week]
    totals = [0] * BASELINE_WEEKS
    by_wd_count: dict[int, int] = defaultdict(int)
    for a in baseline:
        totals[(_week_start(a.start_at.date()) - base_start).days // 7] += 1
        by_wd_count[a.start_at.weekday()] += 1
    total_base = len(baseline)
    mean_week = sum(totals) / BASELINE_WEEKS
    a_fit, b_fit = _linear_fit(totals)
    # Tendencia amortiguada: se limita la pendiente y la recta se re-centra en el promedio.
    b_fit = max(-TREND_CAP * mean_week, min(TREND_CAP * mean_week, b_fit))
    a_fit = mean_week - b_fit * (BASELINE_WEEKS - 1) / 2
    trend_pct = (b_fit / mean_week * 100) if mean_week else 0.0
    avg_blocked = (sum(_minutes(a) for a in baseline) / total_base) if total_base else 30.0
    base_paid = [a.price_paid_cents for a in baseline if a.price_paid_cents is not None]
    base_ticket = (sum(base_paid) / len(base_paid)) if base_paid else 0.0

    def model_for(d: date) -> float:
        if not total_base:
            return 0.0
        x = BASELINE_WEEKS + (_week_start(d) - current_week).days // 7
        return max(TREND_FLOOR * mean_week, a_fit + b_fit * x) * by_wd_count[d.weekday()] / total_base

    booked_n: dict[date, int] = defaultdict(int)
    booked_min: dict[date, float] = defaultdict(float)
    for a in booked:
        booked_n[a.start_at.date()] += 1
        booked_min[a.start_at.date()] += _minutes(a)

    fut_days = _days_between(max(start, today), end, open_days) if end >= today else []
    daily, weekly = [], {}
    for d in fut_days:
        # Un día nunca se prevé por debajo de lo que ya tiene reservado.
        expected = max(model_for(d), booked_n[d])
        occ = _pct(max(model_for(d) * avg_blocked, booked_min[d]), open_min)
        daily.append({"date": d.isoformat(), "expected": round(expected, 1), "booked": booked_n[d],
                      "occupancy_pct": occ})
        w = weekly.setdefault(_week_start(d), {"week_start": _week_start(d).isoformat(), "expected": 0.0, "booked": 0})
        w["expected"] += expected
        w["booked"] += booked_n[d]
    for w in weekly.values():
        w["additional"] = round(w["expected"] - w["booked"], 1)
        w["expected"] = round(w["expected"], 1)

    by_weekday = []
    for wd in open_days:
        vals = [x["occupancy_pct"] for x in daily if date.fromisoformat(x["date"]).weekday() == wd]
        by_weekday.append({"weekday": WEEKDAY_SHORT[wd],
                           "occupancy_pct": round(sum(vals) / len(vals), 1) if vals else None})
    weekday_avg = _classify(by_weekday)

    expected_total = sum(x["expected"] for x in daily)
    booked_total = sum(x["booked"] for x in daily)
    additional = max(0.0, expected_total - booked_total)
    kpis = {
        "expected": round(expected_total, 1),
        "booked": booked_total,
        "additional": round(additional, 1),
        "additional_revenue_cents": round(additional * base_ticket),
        "occupancy_pct": round(sum(x["occupancy_pct"] for x in daily) / len(daily), 1) if daily else 0.0,
        "trend_pct_per_week": round(trend_pct, 1),
    }
    if not fut_days:
        suggestions = [{"level": "info", "text": "El rango elegido termina antes de hoy: no hay días que prever."}]
    elif not total_base:
        suggestions = [_NO_DATA]
    else:
        suggestions = _forecast_suggestions(service.name if service else None, by_weekday, weekday_avg, trend_pct)
    return {
        "available": bool(fut_days),
        "kpis": kpis,
        "weekly": [weekly[k] for k in sorted(weekly)],
        "daily": daily,
        "by_weekday": by_weekday,
        "suggestions": suggestions,
    }


# ---------- Sugerencias ----------
_NO_DATA = {"level": "info", "text": "Aún no hay suficiente histórico para generar sugerencias."}


def _mean(items: list[dict]) -> int:
    return round(sum(x["occupancy_pct"] for x in items) / len(items))


def _names(items: list[dict]) -> str:
    full_name = dict(zip(WEEKDAY_SHORT, WEEKDAY_PLURAL))
    return _join([full_name[w["weekday"]] for w in items])


def _cancel_text(cancel_pct: float) -> Optional[dict]:
    if cancel_pct >= CANCEL_ALERT:
        return {"level": "low", "text": (
            f"El {cancel_pct:.0f} % de las citas del periodo se cancelaron: refuerza los recordatorios "
            "o considera pedir un depósito.")}
    return None


def _real_suggestions(registered, by_weekday, weekday_avg, by_hour, hour_avg, occupancy,
                      by_service, cancel_pct) -> list[dict]:
    """Reglas sobre datos reales que traducen la ocupación en acciones de precio e inventario."""
    if not registered:
        return [{"level": "info", "text": "No hay citas registradas en el rango elegido."}]
    out = []
    days = [w for w in by_weekday if w["occupancy_pct"] is not None]
    full = [w for w in days if w["occupancy_pct"] >= HIGH_OCCUPANCY]
    busy = [w for w in days if w["level"] == "high" and w not in full]
    quiet = [w for w in days if w["level"] == "low"]
    if full:
        out.append({"level": "high", "text": (
            f"Los {_names(full)} estuvieron casi llenos (≈ {_mean(full)} % de ocupación): "
            "considera subir el precio esos días o ampliar el horario de atención.")})
    if busy:
        out.append({"level": "high", "text": (
            f"Mayor demanda los {_names(busy)} (≈ {_mean(busy)} % frente a un promedio de {round(weekday_avg)} %): "
            "son los mejores días para precios más altos o para reforzar la atención.")})
    if quiet:
        out.append({"level": "low", "text": (
            f"Menor demanda los {_names(quiet)} (≈ {_mean(quiet)} % frente a un promedio de {round(weekday_avg)} %): "
            "considera una promoción o descuento para esos días.")})
    if occupancy and occupancy < LOW_OCCUPANCY:
        out.append({"level": "info", "text": (
            f"La ocupación del periodo es ≈ {round(occupancy)} %: hay capacidad libre para captar más clientes "
            "(campañas, convenios o paquetes).")})

    peak = [h for h in by_hour if h["level"] == "high"]
    slow = [h for h in by_hour if h["level"] == "low"]
    if peak:
        out.append({"level": "high", "text": (
            f"Horas pico: {_join([h['hour'] for h in peak])} (≈ {_mean(peak)} % frente a {round(hour_avg)} % de promedio): "
            "candidatas a precio de hora punta.")})
    if slow:
        out.append({"level": "low", "text": (
            f"Horas flojas: {_join([h['hour'] for h in slow])} (≈ {_mean(slow)} %): ofrece descuentos en esos horarios.")})

    extra = _cancel_text(cancel_pct)
    if extra:
        out.append(extra)
    revenue = sum(s["revenue_cents"] for s in by_service)
    if revenue:
        top = by_service[0]
        out.append({"level": "info", "text": (
            f"«{top['service']}» genera el {round(top['revenue_cents'] / revenue * 100)} % de los ingresos del periodo: "
            "prioriza su disponibilidad.")})
    return out


def _real_service_suggestions(name, registered, cancel_pct, by_service, service_id) -> list[dict]:
    """Con un servicio filtrado la ocupación de la agenda no aplica: se describe su patrón real."""
    if not registered:
        return [{"level": "info", "text": f"«{name}» no tiene citas registradas en el rango elegido."}]
    by_day: dict[int, int] = defaultdict(int)
    by_hour: dict[int, int] = defaultdict(int)
    for a in registered:
        by_day[a.start_at.weekday()] += 1
        by_hour[a.start_at.hour] += 1
    peak_day, peak_hour = max(by_day, key=by_day.get), max(by_hour, key=by_hour.get)
    out = [{"level": "info", "text": (
        f"«{name}» se concentra los {WEEKDAY_PLURAL[peak_day]} y alrededor de las {peak_hour:02d}:00: "
        "asegura disponibilidad en esa franja.")}]
    extra = _cancel_text(cancel_pct)
    if extra:
        out.append(extra)
    revenue = sum(s["revenue_cents"] for s in by_service)
    mine = next((s for s in by_service if s["service_id"] == service_id), None)
    if revenue and mine:
        out.append({"level": "info", "text": (
            f"«{name}» representa el {round(mine['revenue_cents'] / revenue * 100)} % de los ingresos del periodo.")})
    return out


def _forecast_suggestions(service_name, by_weekday, weekday_avg, trend_pct) -> list[dict]:
    """Sugerencias de la previsión: siempre dicen que son estimaciones."""
    out = []
    subject = f"la demanda de «{service_name}»" if service_name else "la demanda"
    if not service_name:
        days = [w for w in by_weekday if w["occupancy_pct"] is not None]
        full = [w for w in days if w["occupancy_pct"] >= HIGH_OCCUPANCY]
        busy = [w for w in days if w["level"] == "high" and w not in full]
        quiet = [w for w in days if w["level"] == "low"]
        if full:
            out.append({"level": "high", "text": (
                f"Previsión: los {_names(full)} estarían casi llenos (≈ {_mean(full)} %): "
                "considera subir el precio o ampliar el horario.")})
        if busy:
            out.append({"level": "high", "text": (
                f"Previsión: mayor demanda esperada los {_names(busy)} (≈ {_mean(busy)} % frente a "
                f"{round(weekday_avg)} %): planifica más atención esos días.")})
        if quiet:
            out.append({"level": "low", "text": (
                f"Previsión: menor demanda esperada los {_names(quiet)} (≈ {_mean(quiet)} %): "
                "buen momento para promociones.")})
    if trend_pct >= TREND_ALERT:
        out.append({"level": "high", "text": (
            f"Previsión: {subject} crece ≈ {trend_pct:.1f} % por semana (últimas {BASELINE_WEEKS} semanas): "
            "revisa si la capacidad actual alcanzará.")})
    elif trend_pct <= -TREND_ALERT:
        out.append({"level": "low", "text": (
            f"Previsión: {subject} cae ≈ {abs(trend_pct):.1f} % por semana (últimas {BASELINE_WEEKS} semanas): "
            "considera campañas para recuperar clientes.")})
    if not out:
        out.append({"level": "info", "text": "Previsión: la demanda esperada es estable, sin días que se destaquen."})
    return out
