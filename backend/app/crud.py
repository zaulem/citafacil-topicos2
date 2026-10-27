"""Operaciones de base de datos (Create/Read/Update/Delete)."""
from __future__ import annotations

import secrets
from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from . import models, schemas


# ---------- Servicios ----------
def list_services(db: Session, only_active: bool = True) -> list[models.Service]:
    q = db.query(models.Service)
    if only_active:
        q = q.filter(models.Service.active.is_(True))
    return q.order_by(models.Service.id).all()


def get_service(db: Session, service_id: int) -> Optional[models.Service]:
    return db.query(models.Service).filter(models.Service.id == service_id).first()


def create_service(db: Session, data: schemas.ServiceCreate) -> models.Service:
    obj = models.Service(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_service(db: Session, service: models.Service, data: schemas.ServiceUpdate) -> models.Service:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(service, key, value)
    db.commit()
    db.refresh(service)
    return service


def delete_service(db: Session, service: models.Service) -> None:
    db.delete(service)
    db.commit()


# ---------- Clientes ----------
def get_customer_by_email(db: Session, email: str) -> Optional[models.Customer]:
    return db.query(models.Customer).filter(models.Customer.email == email.strip().lower()).first()


def create_customer(db: Session, data: schemas.CustomerRegister, password_hash: str) -> models.Customer:
    obj = models.Customer(
        email=data.email,
        password_hash=password_hash,
        name=data.name.strip(),
        phone=data.phone,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def save_card(db: Session, customer: models.Customer, card: schemas.CardIn) -> models.PaymentMethod:
    """Guarda la tarjeta del cliente (reemplaza la anterior: una por cliente).
    Solo se conservan marca, últimos 4 dígitos y vencimiento."""
    pm = customer.payment_method or models.PaymentMethod(customer_id=customer.id)
    pm.brand = card.brand
    pm.last4 = card.number[-4:]
    pm.exp_month = card.exp_month
    pm.exp_year = card.exp_year
    pm.token = "tok_" + secrets.token_urlsafe(16)
    db.add(pm)
    db.commit()
    db.refresh(pm)
    return pm


def delete_card(db: Session, card: models.PaymentMethod) -> None:
    db.delete(card)
    db.commit()


# ---------- Citas ----------
def create_appointment(
    db: Session,
    data: schemas.AppointmentCreate,
    service: models.Service,
    end_at: datetime,
    customer: Optional[models.Customer] = None,
    receipt: Optional[dict] = None,
) -> models.Appointment:
    """Crea la cita. `receipt` ({brand, last4}) es el comprobante del pago simulado."""
    obj = models.Appointment(
        customer_id=customer.id if customer else None,
        payment_status=models.PAYMENT_PAID if receipt else models.PAYMENT_UNPAID,
        price_paid_cents=service.price_cents if receipt else None,
        payment_brand=receipt["brand"] if receipt else None,
        payment_last4=receipt["last4"] if receipt else None,
        customer_name=data.customer_name.strip(),
        customer_phone=data.customer_phone,
        service_id=service.id,
        start_at=data.start_at,
        end_at=end_at,
        notes=(data.notes or "").strip(),
        status=models.STATUS_PENDING,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_customer_appointments(db: Session, customer_id: int) -> list[models.Appointment]:
    """Reservas de un cliente, de la más reciente a la más antigua (US-05)."""
    return (
        db.query(models.Appointment)
        .filter(models.Appointment.customer_id == customer_id)
        .order_by(models.Appointment.start_at.desc())
        .all()
    )


def cancel_appointment(db: Session, appt: models.Appointment) -> models.Appointment:
    """Cancela la cita; si estaba pagada, el pago (simulado) se reembolsa completo."""
    appt.status = models.STATUS_CANCELLED
    if appt.payment_status == models.PAYMENT_PAID:
        appt.payment_status = models.PAYMENT_REFUNDED
    db.commit()
    db.refresh(appt)
    return appt


def reschedule_appointment(db: Session, appt: models.Appointment, start_at: datetime) -> models.Appointment:
    """Mueve la cita conservando su duración y su pago; el recordatorio se vuelve a enviar."""
    duration = appt.end_at - appt.start_at
    appt.start_at = start_at
    appt.end_at = start_at + duration
    appt.reminder_sent = False
    db.commit()
    db.refresh(appt)
    return appt


def list_appointments(
    db: Session, status: Optional[str] = None, day: Optional[date] = None
) -> list[models.Appointment]:
    q = db.query(models.Appointment)
    if status:
        q = q.filter(models.Appointment.status == status)
    if day:
        q = q.filter(
            models.Appointment.start_at >= datetime.combine(day, time.min),
            models.Appointment.start_at <= datetime.combine(day, time.max),
        )
    return q.order_by(models.Appointment.start_at).all()


def get_appointment(db: Session, appt_id: int) -> Optional[models.Appointment]:
    return db.query(models.Appointment).filter(models.Appointment.id == appt_id).first()


def set_status(db: Session, appt: models.Appointment, status: str) -> models.Appointment:
    """Cambio de estado del admin. Cancelar reembolsa el pago igual que cuando cancela
    el cliente (H-31). La validez de la transición la revisa el endpoint."""
    if status == models.STATUS_CANCELLED:
        return cancel_appointment(db, appt)
    appt.status = status
    db.commit()
    db.refresh(appt)
    return appt


def delete_appointment(db: Session, appt: models.Appointment) -> None:
    db.delete(appt)
    db.commit()


def stats(db: Session) -> dict:
    from .utils import local_now

    def count(status: str) -> int:
        return db.query(models.Appointment).filter(models.Appointment.status == status).count()

    upcoming = (
        db.query(models.Appointment)
        .filter(
            models.Appointment.start_at >= local_now(),
            models.Appointment.status.in_([models.STATUS_PENDING, models.STATUS_CONFIRMED]),
        )
        .count()
    )
    return {
        "total": db.query(models.Appointment).count(),
        "pending": count(models.STATUS_PENDING),
        "confirmed": count(models.STATUS_CONFIRMED),
        "cancelled": count(models.STATUS_CANCELLED),
        "done": count(models.STATUS_DONE),
        "upcoming": upcoming,
    }
