"""Cuentas de cliente (US-01): registro, inicio/cierre de sesión y datos propios.
Mis reservas (US-05): ver, cancelar y reprogramar las reservas propias.

Limitación conocida: no se verifica que el correo pertenezca al cliente
(la app no envía correos).
"""
from __future__ import annotations

import math
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..auth import create_session, hash_password, require_session, verify_password
from ..availability import is_slot_free
from ..config import settings
from ..database import get_db
from ..notifications import cancellation_message, reschedule_message, send_whatsapp
from ..utils import local_now, utc_now

router = APIRouter(prefix="/api", tags=["Cuentas"])

# Mismo mensaje para correo inexistente y contraseña incorrecta: no se revela
# qué correos están registrados.
_BAD_CREDENTIALS = "Correo o contraseña incorrectos."


def _session_out(token: str, session: models.CustomerSession) -> schemas.SessionOut:
    return schemas.SessionOut(
        token=token,
        expires_at=session.expires_at,
        customer=schemas.CustomerOut.model_validate(session.customer),
    )


@router.post(
    "/auth/register", response_model=schemas.SessionOut, status_code=201, summary="Crear cuenta"
)
def register(payload: schemas.CustomerRegister, db: Session = Depends(get_db)):
    if crud.get_customer_by_email(db, payload.email):
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo.")
    customer = crud.create_customer(db, payload, hash_password(payload.password))
    token, session = create_session(db, customer)
    return _session_out(token, session)


@router.post("/auth/login", response_model=schemas.SessionOut, summary="Iniciar sesión")
def login(payload: schemas.CustomerLogin, db: Session = Depends(get_db)):
    customer = crud.get_customer_by_email(db, payload.email)
    if not customer:
        raise HTTPException(status_code=401, detail=_BAD_CREDENTIALS)

    now = utc_now()
    if customer.locked_until and customer.locked_until > now:
        minutes = math.ceil((customer.locked_until - now).total_seconds() / 60)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Cuenta bloqueada por intentos fallidos. Intenta de nuevo en {minutes} min.",
        )

    if not verify_password(payload.password, customer.password_hash):
        customer.failed_logins += 1
        if customer.failed_logins >= settings.login_max_attempts:
            customer.failed_logins = 0
            customer.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
        db.commit()
        raise HTTPException(status_code=401, detail=_BAD_CREDENTIALS)

    customer.failed_logins = 0
    customer.locked_until = None
    db.commit()
    token, session = create_session(db, customer)
    return _session_out(token, session)


@router.post("/auth/logout", response_model=schemas.MessageOut, summary="Cerrar sesión")
def logout(session: models.CustomerSession = Depends(require_session), db: Session = Depends(get_db)):
    db.delete(session)
    db.commit()
    return {"detail": "Sesión cerrada."}


@router.get("/me", response_model=schemas.CustomerOut, summary="Mis datos")
def me(session: models.CustomerSession = Depends(require_session)):
    return session.customer


# ---------- Tarjeta guardada (una por cliente) ----------
@router.get("/me/card", response_model=schemas.CardOut, summary="Mi tarjeta guardada")
def my_card(session: models.CustomerSession = Depends(require_session)):
    card = session.customer.payment_method
    if not card:
        raise HTTPException(status_code=404, detail="No tienes una tarjeta guardada.")
    return card


@router.put("/me/card", response_model=schemas.CardOut, summary="Guardar o reemplazar mi tarjeta")
def put_card(
    payload: schemas.CardIn,
    session: models.CustomerSession = Depends(require_session),
    db: Session = Depends(get_db),
):
    return crud.save_card(db, session.customer, payload)


@router.delete("/me/card", response_model=schemas.MessageOut, summary="Eliminar mi tarjeta")
def delete_card(session: models.CustomerSession = Depends(require_session), db: Session = Depends(get_db)):
    card = session.customer.payment_method
    if not card:
        raise HTTPException(status_code=404, detail="No tienes una tarjeta guardada.")
    crud.delete_card(db, card)
    return {"detail": "Tarjeta eliminada."}


# ---------- Mis reservas (US-05) ----------
def _state(appt: models.Appointment, now) -> str:
    if appt.status == models.STATUS_CANCELLED:
        return "cancelled"
    return "done" if appt.start_at <= now else "scheduled"


def _deadline(appt: models.Appointment):
    return appt.start_at - timedelta(hours=settings.cancel_min_hours)


def _my_out(appt: models.Appointment, now) -> schemas.MyAppointmentOut:
    state = _state(appt, now)
    return schemas.MyAppointmentOut(
        **schemas.AppointmentOut.model_validate(appt).model_dump(),
        state=state,
        can_change=state == "scheduled" and now <= _deadline(appt),
        change_deadline=_deadline(appt),
    )


def _own_changeable(db: Session, session: models.CustomerSession, appt_id: int, action: str) -> models.Appointment:
    """La cita debe ser del cliente (si no, 404: no se revela que existe), estar
    programada y dentro del plazo de CANCEL_MIN_HOURS antes de la cita."""
    appt = crud.get_appointment(db, appt_id)
    if not appt or appt.customer_id != session.customer_id:
        raise HTTPException(status_code=404, detail="Reserva no encontrada.")
    now = local_now()
    if _state(appt, now) != "scheduled":
        raise HTTPException(status_code=409, detail=f"Esta reserva ya no se puede {action}: está cancelada o ya pasó.")
    if now > _deadline(appt):
        raise HTTPException(
            status_code=409,
            detail=f"Solo se puede {action} hasta {settings.cancel_min_hours} h antes de la cita.",
        )
    return appt


@router.get("/me/appointments", response_model=schemas.MyAppointmentsOut, summary="Mis reservas")
def my_appointments(session: models.CustomerSession = Depends(require_session), db: Session = Depends(get_db)):
    now = local_now()
    items = [_my_out(a, now) for a in crud.list_customer_appointments(db, session.customer_id)]
    counts = {s: sum(1 for x in items if x.state == s) for s in ("scheduled", "done", "cancelled")}
    return schemas.MyAppointmentsOut(
        cancel_min_hours=settings.cancel_min_hours,
        counts=schemas.MyAppointmentsCounts(total=len(items), **counts),
        appointments=items,
    )


@router.post("/me/appointments/{appt_id}/cancel", response_model=schemas.MyAppointmentOut, summary="Cancelar mi reserva")
def cancel_my_appointment(
    appt_id: int,
    session: models.CustomerSession = Depends(require_session),
    db: Session = Depends(get_db),
):
    appt = crud.cancel_appointment(db, _own_changeable(db, session, appt_id, "cancelar"))
    send_whatsapp(appt.customer_phone, cancellation_message(
        settings.business_name, appt.customer_name, appt.service.name, appt.start_at))
    return _my_out(appt, local_now())


@router.post("/me/appointments/{appt_id}/reschedule", response_model=schemas.MyAppointmentOut,
             summary="Reprogramar mi reserva")
def reschedule_my_appointment(
    appt_id: int,
    payload: schemas.RescheduleIn,
    session: models.CustomerSession = Depends(require_session),
    db: Session = Depends(get_db),
):
    """Solo cambia fecha y hora (mismo servicio y mismo pago). El horario actual de la
    cita no cuenta como ocupado al buscar el nuevo."""
    appt = _own_changeable(db, session, appt_id, "reprogramar")
    if payload.start_at == appt.start_at:
        raise HTTPException(status_code=422, detail="Elige un horario distinto al actual.")
    if not is_slot_free(db, appt.service, payload.start_at, exclude_id=appt.id):
        raise HTTPException(status_code=409, detail="Ese horario ya no está disponible. Por favor elige otro.")
    appt = crud.reschedule_appointment(db, appt, payload.start_at)
    send_whatsapp(appt.customer_phone, reschedule_message(
        settings.business_name, appt.customer_name, appt.service.name, appt.start_at))
    return _my_out(appt, local_now())
