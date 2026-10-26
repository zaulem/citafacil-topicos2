"""Lógica de disponibilidad: genera horarios libres y evita el doble-booking."""
from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from . import models
from .config import settings
from .utils import local_now

# Estados de un día en el calendario mensual
DAY_AVAILABLE = "available"
DAY_FULL = "full"
DAY_CLOSED = "closed"
DAY_PAST = "past"
DAY_OUT_OF_RANGE = "out_of_range"


def max_booking_date() -> date:
    """Último día reservable: hoy + `booking_horizon_months` meses (mismo día del mes,
    o el último día si ese mes es más corto)."""
    today = local_now().date()
    y, m = divmod(today.month - 1 + settings.booking_horizon_months, 12)
    year, month = today.year + y, m + 1
    return date(year, month, min(today.day, calendar.monthrange(year, month)[1]))


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """True si dos intervalos [inicio, fin) se solapan."""
    return a_start < b_end and b_start < a_end


def _booked_that_day(db: Session, day: date) -> list[models.Appointment]:
    day_start = datetime.combine(day, time.min)
    day_end = datetime.combine(day, time.max)
    return (
        db.query(models.Appointment)
        .filter(
            models.Appointment.status != models.STATUS_CANCELLED,
            models.Appointment.start_at >= day_start,
            models.Appointment.start_at <= day_end,
        )
        .all()
    )


def generate_slots(db: Session, service: models.Service, day: date) -> list[str]:
    """Horas 'HH:MM' disponibles para un servicio en un día dado."""
    if day.weekday() in settings.closed_weekdays_set or day > max_booking_date():
        return []

    duration = timedelta(minutes=service.duration_min)
    open_dt = datetime.combine(day, time(hour=settings.open_hour))
    close_dt = datetime.combine(day, time(hour=settings.close_hour))
    booked = _booked_that_day(db, day)
    now = local_now()

    slots: list[str] = []
    cursor = open_dt
    step = timedelta(minutes=settings.slot_interval_minutes)
    while cursor + duration <= close_dt:
        slot_end = cursor + duration
        if cursor <= now:  # no ofrecer horas ya pasadas
            cursor += step
            continue
        conflict = any(_overlaps(cursor, slot_end, b.start_at, b.end_at) for b in booked)
        if not conflict:
            slots.append(cursor.strftime("%H:%M"))
        cursor += step
    return slots


def is_slot_free(db: Session, service: models.Service, start_at: datetime) -> bool:
    """Valida que un inicio concreto esté dentro de horario y libre."""
    if start_at.weekday() in settings.closed_weekdays_set or start_at.date() > max_booking_date():
        return False

    end_at = start_at + timedelta(minutes=service.duration_min)
    open_dt = datetime.combine(start_at.date(), time(hour=settings.open_hour))
    close_dt = datetime.combine(start_at.date(), time(hour=settings.close_hour))
    if start_at < open_dt or end_at > close_dt:
        return False
    if start_at <= local_now():
        return False

    booked = _booked_that_day(db, start_at.date())
    return not any(_overlaps(start_at, end_at, b.start_at, b.end_at) for b in booked)


def month_overview(db: Session, service: models.Service, year: int, month: int) -> list[dict]:
    """Estado de cada día del mes para un servicio: disponible (con nº de horarios
    libres), lleno, cerrado, pasado o fuera del rango reservable."""
    today = local_now().date()
    last_day = max_booking_date()
    duration = timedelta(minutes=service.duration_min)
    days: list[dict] = []
    for n in range(1, calendar.monthrange(year, month)[1] + 1):
        day = date(year, month, n)
        free = 0
        if day < today:
            status = DAY_PAST
        elif day > last_day:
            status = DAY_OUT_OF_RANGE
        elif day.weekday() in settings.closed_weekdays_set:
            status = DAY_CLOSED
        else:
            free = len(generate_slots(db, service, day))
            if free:
                status = DAY_AVAILABLE
            elif day == today and local_now() + duration > datetime.combine(day, time(hour=settings.close_hour)):
                status = DAY_PAST  # hoy ya no alcanza el tiempo: no es "lleno"
            else:
                status = DAY_FULL
        days.append({"date": day.isoformat(), "status": status, "free": free})
    return days
