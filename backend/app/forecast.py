"""Previsión de demanda (US-03) con rango de fechas y filtro por servicio (#20).

Método (explicable sin estadística avanzada):
1. Modelo: se toman las últimas BASELINE_WEEKS semanas completas antes de hoy,
   SIEMPRE las mismas sin importar el rango elegido (si no, un rango solo futuro
   dejaría al modelo sin datos).
2. Tendencia: recta de mínimos cuadrados sobre el total de citas de cada semana.
   La semana futura x se estima como `a + b·x` (la semana actual es x = BASELINE_WEEKS).
3. Ese total semanal se reparte entre los días según el peso histórico de cada día
   de la semana (p. ej., si los sábados concentran el 25 % de las citas, reciben el 25 %).
4. Ocupación = tiempo bloqueado en turnos / tiempo de atención del día. Los turnos son
   el "inventario" de la barbería: una cita de 20 min bloquea un turno de 30 min completo.

El rango elegido solo decide QUÉ se muestra: los días pasados del rango muestran datos
reales y los días desde hoy muestran la previsión y las reservas ya tomadas.
Con un servicio filtrado, todo (modelo incluido) se calcula solo con ese servicio.

Las citas canceladas no cuentan como demanda. Los ingresos usan `price_paid_cents`
(lo que se cobró), no el precio actual del servicio (H-15).
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


def _avg(values: list[float]) -> Optional[float]:
    return round(sum(values) / len(values), 1) if values else None


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
    active = [a for a in rows if a.status != models.STATUS_CANCELLED]
    in_range = [a for a in rows if start <= a.start_at.date() <= end]
    range_active = [a for a in in_range if a.status != models.STATUS_CANCELLED]
    past_active = [a for a in range_active if a.start_at.date() < today]
    future_active = [a for a in range_active if a.start_at.date() >= today]

    # ---------- Modelo (últimas 8 semanas completas antes de hoy) ----------
    baseline = [a for a in active if base_start <= a.start_at.date() < current_week]
    totals = [0] * BASELINE_WEEKS
    by_wd_count: dict[int, int] = defaultdict(int)
    by_hour_count: dict[int, int] = defaultdict(int)
    for a in baseline:
        totals[(_week_start(a.start_at.date()) - base_start).days // 7] += 1
        by_wd_count[a.start_at.weekday()] += 1
        by_hour_count[a.start_at.hour] += 1
    a_fit, b_fit = _linear_fit(totals)
    mean_week = sum(totals) / BASELINE_WEEKS
    trend_pct = (b_fit / mean_week * 100) if mean_week else 0.0
    total_base = len(baseline)
    avg_blocked = (sum(_minutes(a) for a in baseline) / total_base) if total_base else 30.0
    base_paid = [a.price_paid_cents for a in baseline if a.price_paid_cents is not None]
    base_ticket = (sum(base_paid) / len(base_paid)) if base_paid else 0.0

    def expected_for(d: date) -> float:
        if not total_base:
            return 0.0
        x = BASELINE_WEEKS + (_week_start(d) - current_week).days // 7
        return max(0.0, a_fit + b_fit * x) * by_wd_count[d.weekday()] / total_base

    # ---------- Serie diaria del rango ----------
    day_n: dict[date, int] = defaultdict(int)
    day_min: dict[date, float] = defaultdict(float)
    for a in range_active:
        day_n[a.start_at.date()] += 1
        day_min[a.start_at.date()] += _minutes(a)

    days = []
    d = start
    while d <= end:
        if d.weekday() in open_days:
            occ_booked = round(min(100.0, day_min[d] / open_min * 100), 1)
            if d < today:
                days.append({"date": d.isoformat(), "kind": "real", "real": day_n[d], "expected": None,
                             "booked": None, "occupancy_pct": occ_booked, "booked_occupancy_pct": None})
            else:
                exp = expected_for(d)
                days.append({"date": d.isoformat(), "kind": "forecast", "real": None, "expected": round(exp, 1),
                             "booked": day_n[d],
                             "occupancy_pct": round(min(100.0, exp * avg_blocked / open_min * 100), 1),
                             "booked_occupancy_pct": occ_booked})
        d += timedelta(days=1)

    weekly: dict[date, dict] = {}
    for day in days:
        w = weekly.setdefault(_week_start(date.fromisoformat(day["date"])), {"real": 0, "expected": 0.0, "booked": 0})
        w["real"] += day["real"] or 0
        w["expected"] += day["expected"] or 0.0
        w["booked"] += day["booked"] or 0
    weeks = [{"week_start": ws.isoformat(), "real": v["real"], "expected": round(v["expected"], 1),
              "booked": v["booked"]} for ws, v in sorted(weekly.items())]

    # ---------- Ocupación por día de la semana y por hora (dentro del rango) ----------
    by_weekday = []
    for wd in open_days:
        mine = [x for x in days if date.fromisoformat(x["date"]).weekday() == wd]
        real = [x for x in mine if x["kind"] == "real"]
        fc = [x for x in mine if x["kind"] == "forecast"]
        real_pct = _avg([x["occupancy_pct"] for x in real])
        expected_pct = _avg([x["occupancy_pct"] for x in fc])
        by_weekday.append({
            "weekday": WEEKDAY_SHORT[wd],
            "real_occupancy_pct": real_pct,
            "expected_occupancy_pct": expected_pct,
            # la que se usa para clasificar: la prevista si el rango llega al futuro
            "occupancy_pct": expected_pct if expected_pct is not None else real_pct,
        })
    weekday_avg = _classify(by_weekday)

    # Si el rango tiene días pasados se usan citas reales; si es solo futuro, las ya reservadas.
    hour_basis = "real" if any(x["kind"] == "real" for x in days) else "booked"
    hour_appts = past_active if hour_basis == "real" else future_active
    hour_days = sum(1 for x in days if (x["kind"] == "real") == (hour_basis == "real")) or 1
    hour_minutes: dict[int, float] = defaultdict(float)
    for a in hour_appts:
        blocked_end = a.start_at + timedelta(minutes=_minutes(a))
        for h in range(settings.open_hour, settings.close_hour):
            h_start = datetime.combine(a.start_at.date(), time(hour=h))
            overlap = (min(blocked_end, h_start + timedelta(hours=1)) - max(a.start_at, h_start)).total_seconds()
            if overlap > 0:
                hour_minutes[h] += overlap / 60
    by_hour = [
        {"hour": f"{h:02d}:00", "occupancy_pct": round(hour_minutes[h] / (60 * hour_days) * 100, 1)}
        for h in range(settings.open_hour, settings.close_hour)
    ]
    hour_avg = _classify(by_hour)

    # ---------- Servicios (siempre todos, para poder elegir uno y filtrar) ----------
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

    # ---------- KPIs del rango ----------
    expected_total = sum(x["expected"] or 0 for x in days)
    real_revenue = sum(a.price_paid_cents or 0 for a in past_active)
    paid_real = [a.price_paid_cents for a in past_active if a.price_paid_cents is not None]
    past_rows = [a for a in in_range if a.start_at.date() < today]
    cancel_pct = (sum(a.status == models.STATUS_CANCELLED for a in past_rows) / len(past_rows) * 100) if past_rows else 0.0
    kpis = {
        "real_appointments": len(past_active),
        "expected_appointments": round(expected_total, 1),
        "booked_appointments": len(future_active),
        "revenue_cents": round(real_revenue + expected_total * base_ticket),
        "occupancy_pct": _avg([x["occupancy_pct"] for x in days]) or 0.0,
        "avg_ticket_cents": round(sum(paid_real) / len(paid_real)) if paid_real else round(base_ticket),
        "cancellation_rate_pct": round(cancel_pct, 1),
        "trend_pct_per_week": round(trend_pct, 1),
    }

    if service:
        suggestions = _service_suggestions(service.name, total_base, by_wd_count, by_hour_count,
                                           trend_pct, cancel_pct, by_service, service.id)
    else:
        suggestions = _general_suggestions(total_base, by_weekday, weekday_avg, by_hour, hour_avg,
                                           by_service, trend_pct, cancel_pct)

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "today": today.isoformat(),
        "max_date": max_booking_date().isoformat(),
        "service": {"id": service.id, "name": service.name} if service else None,
        "hour_basis": hour_basis,
        "kpis": kpis,
        "weekly": weeks,
        "daily": days,
        "by_weekday": by_weekday,
        "by_hour": by_hour,
        "by_service": by_service,
        "suggestions": suggestions,
    }


# ---------- Sugerencias ----------
_NO_DATA = {"level": "info", "text": "Aún no hay suficiente histórico para generar sugerencias."}


def _trend_text(trend_pct: float, subject: str) -> Optional[dict]:
    if trend_pct >= TREND_ALERT:
        return {"level": "high", "text": f"{subject} crece ≈ {trend_pct:.1f} % por semana: revisa si la capacidad actual alcanzará."}
    if trend_pct <= -TREND_ALERT:
        return {"level": "low", "text": f"{subject} cae ≈ {abs(trend_pct):.1f} % por semana: considera campañas para recuperar clientes."}
    return None


def _cancel_text(cancel_pct: float) -> Optional[dict]:
    if cancel_pct >= CANCEL_ALERT:
        return {"level": "low", "text": (
            f"El {cancel_pct:.0f} % de las citas del periodo se cancelaron: refuerza los recordatorios "
            "o considera pedir un depósito.")}
    return None


def _mean(items: list[dict]) -> int:
    return round(sum(x["occupancy_pct"] for x in items) / len(items))


def _general_suggestions(total_base, by_weekday, weekday_avg, by_hour, hour_avg,
                         by_service, trend_pct, cancel_pct) -> list[dict]:
    """Reglas simples que traducen los datos en acciones de precio e inventario."""
    if not total_base:
        return [_NO_DATA]
    out = []
    full_name = dict(zip(WEEKDAY_SHORT, WEEKDAY_PLURAL))
    names = lambda items: _join([full_name[w["weekday"]] for w in items])

    full = [w for w in by_weekday if w["occupancy_pct"] is not None and w["occupancy_pct"] >= HIGH_OCCUPANCY]
    busy = [w for w in by_weekday if w["level"] == "high" and w not in full]
    quiet = [w for w in by_weekday if w["level"] == "low"]
    if full:
        out.append({"level": "high", "text": (
            f"Los {names(full)} están casi llenos (≈ {_mean(full)} % de ocupación): "
            "considera subir el precio esos días o ampliar el horario de atención.")})
    if busy:
        out.append({"level": "high", "text": (
            f"Mayor demanda los {names(busy)} (≈ {_mean(busy)} % frente a un promedio de {round(weekday_avg)} %): "
            "son los mejores días para precios más altos o para reforzar la atención.")})
    if quiet:
        out.append({"level": "low", "text": (
            f"Menor demanda los {names(quiet)} (≈ {_mean(quiet)} % frente a un promedio de {round(weekday_avg)} %): "
            "considera una promoción o descuento para esos días.")})
    if weekday_avg and weekday_avg < LOW_OCCUPANCY:
        out.append({"level": "info", "text": (
            f"La ocupación promedio es ≈ {round(weekday_avg)} %: hay capacidad libre para captar más clientes "
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

    for extra in (_trend_text(trend_pct, "La demanda"), _cancel_text(cancel_pct)):
        if extra:
            out.append(extra)

    revenue = sum(s["revenue_cents"] for s in by_service)
    if revenue:
        top = by_service[0]
        out.append({"level": "info", "text": (
            f"«{top['service']}» genera el {round(top['revenue_cents'] / revenue * 100)} % de los ingresos del periodo: "
            "prioriza su disponibilidad.")})
    return out


def _service_suggestions(name, total_base, by_wd_count, by_hour_count, trend_pct, cancel_pct,
                         by_service, service_id) -> list[dict]:
    """Con un servicio filtrado la ocupación de la agenda no aplica: se describe su patrón."""
    if not total_base:
        return [_NO_DATA]
    out = []
    peak_day = max(by_wd_count, key=by_wd_count.get)
    peak_hour = max(by_hour_count, key=by_hour_count.get)
    out.append({"level": "info", "text": (
        f"«{name}» se concentra los {WEEKDAY_PLURAL[peak_day]} y alrededor de las {peak_hour:02d}:00 "
        f"(últimas {BASELINE_WEEKS} semanas): asegura disponibilidad en esa franja.")})
    for extra in (_trend_text(trend_pct, f"La demanda de «{name}»"), _cancel_text(cancel_pct)):
        if extra:
            out.append(extra)
    revenue = sum(s["revenue_cents"] for s in by_service)
    mine = next((s for s in by_service if s["service_id"] == service_id), None)
    if revenue and mine:
        out.append({"level": "info", "text": (
            f"«{name}» representa el {round(mine['revenue_cents'] / revenue * 100)} % de los ingresos del periodo.")})
    return out
