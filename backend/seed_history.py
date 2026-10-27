"""Genera ~3 meses de citas pasadas (~300) y algunas futuras para la previsión (US-03).

Uso (después de seed.py):  python seed_history.py

Patrones simulados: más demanda viernes y sábados, horas pico al mediodía y al
final de la tarde, crecimiento leve en el tiempo, más cortes que tintes y ~8 %
de cancelaciones. Cada día tiene además una variación al azar: como en un negocio
real, hay días flojos y días buenos; ninguno se acerca a llenarse.
Respeta el horario, los días cerrados y no solapa citas.
Es reproducible (semilla fija) y no vuelve a generar si ya hay histórico.
"""
from __future__ import annotations

import random
import sys
from datetime import datetime, time, timedelta

from app import models
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.utils import local_now

DAYS_BACK = 91         # ~3 meses de histórico (coherente con el rango máximo de la vista)
DAYS_AHEAD = 21        # reservas futuras ya tomadas (para comparar con la previsión)
SEED = 42

# Probabilidad de que un horario se reserve: día × hora × variación del día × crecimiento.
# Calibrado para ~300 citas en 3 meses (≈ 4 por día abierto).
WEEKDAY_FACTOR = {0: 0.15, 1: 0.21, 2: 0.26, 3: 0.30, 4: 0.45, 5: 0.57}  # lun..sáb
DAY_VARIATION = (0.4, 1.6)  # multiplicador al azar por día: días flojos y días buenos
HOUR_FACTOR = {10: 0.5, 11: 0.7, 12: 0.9, 13: 0.8, 14: 0.5, 15: 0.5, 16: 0.7, 17: 0.9, 18: 0.9, 19: 0.6}
SERVICE_WEIGHT = {"Corte de pelo": 0.40, "Corte + Barba": 0.25, "Perfilado de barba": 0.15,
                  "Corte niño": 0.12, "Tinte / Color": 0.08}
NAMES = ["Carlos Pérez", "Luis Gómez", "Andrés Castillo", "Miguel Herrera", "José Rodríguez",
         "Daniel Vargas", "Ricardo Moreno", "Fernando Ríos", "Javier Sánchez", "Pablo Díaz",
         "Kevin Batista", "Ana Torres", "Sofía Delgado", "Mateo Quintero", "Diego Samaniego"]


def run() -> None:
    Base.metadata.create_all(bind=engine)
    rnd = random.Random(SEED)
    db = SessionLocal()
    try:
        services = {s.name: s for s in db.query(models.Service).filter(models.Service.active.is_(True))}
        weighted = [(services[n], w) for n, w in SERVICE_WEIGHT.items() if n in services]
        if not weighted:
            print("• No hay servicios de ejemplo: ejecuta primero  python seed.py")
            return
        today = local_now().date()
        if db.query(models.Appointment).filter(
            models.Appointment.start_at < datetime.combine(today - timedelta(days=7), time.min)
        ).count():
            print("• Ya existe histórico; no se vuelve a generar.")
            return

        svcs, weights = zip(*weighted)
        step = timedelta(minutes=settings.slot_interval_minutes)
        created = 0
        for offset in range(-DAYS_BACK, DAYS_AHEAD + 1):
            day = today + timedelta(days=offset)
            if offset == 0 or day.weekday() in settings.closed_weekdays_set:
                continue
            growth = 0.8 + 0.2 * (offset + DAYS_BACK) / DAYS_BACK   # 0.8 -> 1.0 hasta hoy
            # A futuro solo una parte ya está reservada: menos cuanto más lejos.
            booked_share = 1.0 if offset < 0 else max(0.1, 0.7 - 0.6 * offset / DAYS_AHEAD)
            day_factor = rnd.uniform(*DAY_VARIATION)
            existing = db.query(models.Appointment).filter(
                models.Appointment.start_at >= datetime.combine(day, time.min),
                models.Appointment.start_at <= datetime.combine(day, time.max),
                models.Appointment.status != models.STATUS_CANCELLED,
            ).all()
            busy = [(a.start_at, a.end_at) for a in existing]
            cursor = datetime.combine(day, time(hour=settings.open_hour))
            close = datetime.combine(day, time(hour=settings.close_hour))
            while cursor < close:
                p = (WEEKDAY_FACTOR.get(day.weekday(), 0.2) * HOUR_FACTOR.get(cursor.hour, 0.5)
                     * day_factor * growth * booked_share)
                svc = rnd.choices(svcs, weights)[0]
                end = cursor + timedelta(minutes=svc.duration_min)
                free = end <= close and not any(cursor < b_end and b_start < end for b_start, b_end in busy)
                if rnd.random() < p and free:
                    past = offset < 0
                    status = (models.STATUS_CANCELLED if rnd.random() < 0.08
                              else models.STATUS_DONE if past else rnd.choice([models.STATUS_PENDING, models.STATUS_CONFIRMED]))
                    db.add(models.Appointment(
                        customer_name=rnd.choice(NAMES),
                        customer_phone=f"+5076{rnd.randint(1000000, 9999999)}",
                        service_id=svc.id, start_at=cursor, end_at=end, status=status,
                        payment_status=models.PAYMENT_PAID, price_paid_cents=svc.price_cents,
                        payment_brand=rnd.choice(["Visa", "Mastercard"]),
                        payment_last4=f"{rnd.randint(0, 9999):04d}",
                        reminder_sent=past,
                        created_at=cursor - timedelta(days=rnd.randint(1, 14)),
                    ))
                    created += 1
                    if status != models.STATUS_CANCELLED:
                        busy.append((cursor, end))
                    # avanzar al siguiente inicio de la grilla después de la cita
                    while cursor < end:
                        cursor += step
                else:
                    cursor += step
        db.commit()
        print(f"✔ Histórico generado: {created} citas ({DAYS_BACK} días atrás y {DAYS_AHEAD} adelante).")
    finally:
        db.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")  # H-04: consolas de Windows (cp1252)
    run()
