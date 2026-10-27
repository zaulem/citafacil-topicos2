"""Endpoints públicos: config, servicios, disponibilidad y creación de reservas."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import crud, models, payments, schemas
from ..auth import optional_customer
from ..availability import generate_slots, is_slot_free, max_booking_date, month_overview
from ..config import settings
from ..database import get_db
from ..notifications import confirmation_message, send_whatsapp
from ..utils import local_now

router = APIRouter(prefix="/api", tags=["Público"])


@router.get("/config", response_model=schemas.ConfigOut, summary="Configuración del negocio")
def get_config():
    return schemas.ConfigOut(
        business_name=settings.business_name,
        timezone=settings.business_timezone,
        currency=settings.currency,
        open_hour=settings.open_hour,
        close_hour=settings.close_hour,
        slot_interval_minutes=settings.slot_interval_minutes,
        closed_weekdays=sorted(settings.closed_weekdays_set),
    )


@router.get("/services", response_model=list[schemas.ServiceOut], summary="Servicios activos")
def get_services(db: Session = Depends(get_db)):
    return crud.list_services(db, only_active=True)


_EXCLUDE_HELP = "ID de una cita propia que se está reprogramando: su horario no cuenta como ocupado (requiere sesión)"


def _own_exclude(db: Session, customer: Optional[models.Customer], exclude_id: Optional[int]) -> Optional[int]:
    """Solo se excluye la cita si es del cliente con sesión; si no, se ignora en silencio
    (así el parámetro no sirve para espiar la agenda de otros)."""
    if exclude_id is None or customer is None:
        return None
    appt = crud.get_appointment(db, exclude_id)
    return exclude_id if appt and appt.customer_id == customer.id else None


@router.get("/availability", response_model=list[str], summary="Horarios disponibles")
def get_availability(
    service_id: int = Query(..., description="ID del servicio"),
    day: date = Query(..., alias="date", description="Fecha en formato YYYY-MM-DD"),
    exclude_id: Optional[int] = Query(None, description=_EXCLUDE_HELP),
    db: Session = Depends(get_db),
    customer: Optional[models.Customer] = Depends(optional_customer),
):
    service = crud.get_service(db, service_id)
    if not service or not service.active:
        raise HTTPException(status_code=404, detail="Servicio no encontrado.")
    return generate_slots(db, service, day, _own_exclude(db, customer, exclude_id))


@router.get(
    "/availability/month",
    response_model=schemas.MonthAvailabilityOut,
    summary="Disponibilidad del mes (calendario)",
)
def get_month_availability(
    service_id: int = Query(..., description="ID del servicio"),
    month: Optional[str] = Query(
        None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="Mes YYYY-MM (por defecto, el actual)"
    ),
    exclude_id: Optional[int] = Query(None, description=_EXCLUDE_HELP),
    db: Session = Depends(get_db),
    customer: Optional[models.Customer] = Depends(optional_customer),
):
    service = crud.get_service(db, service_id)
    if not service or not service.active:
        raise HTTPException(status_code=404, detail="Servicio no encontrado.")
    today = local_now().date()
    year, mon = (int(x) for x in month.split("-")) if month else (today.year, today.month)
    return schemas.MonthAvailabilityOut(
        month=f"{year:04d}-{mon:02d}",
        today=today.isoformat(),
        max_date=max_booking_date().isoformat(),
        days=month_overview(db, service, year, mon, _own_exclude(db, customer, exclude_id)),
    )


@router.post(
    "/appointments",
    response_model=schemas.AppointmentOut,
    status_code=201,
    summary="Crear una reserva",
)
def create_appointment(
    payload: schemas.AppointmentCreate,
    db: Session = Depends(get_db),
    customer: Optional[models.Customer] = Depends(optional_customer),
):
    """Con sesión iniciada la cita queda asociada al cliente; sin sesión, es de invitado.

    Orden: horario libre -> cobro simulado -> cita. Si el pago falla no se crea la cita.
    """
    pay = payload.payment
    if (pay.use_saved_card or pay.save_card) and not customer:
        raise HTTPException(status_code=401, detail="Inicia sesión para usar o guardar una tarjeta.")
    service = crud.get_service(db, payload.service_id)
    if not service or not service.active:
        raise HTTPException(status_code=404, detail="Servicio no encontrado.")
    if not is_slot_free(db, service, payload.start_at):
        raise HTTPException(
            status_code=409,
            detail="Ese horario ya no está disponible. Por favor elige otro.",
        )

    if pay.use_saved_card and not customer.payment_method:
        raise HTTPException(status_code=400, detail="No tienes una tarjeta guardada.")
    try:
        if pay.use_saved_card:
            receipt = payments.charge(service.price_cents, saved=customer.payment_method)
        else:
            receipt = payments.charge(service.price_cents, number=pay.card.number)
    except payments.PaymentDeclined as e:
        raise HTTPException(status_code=402, detail=str(e))
    if pay.save_card:
        crud.save_card(db, customer, pay.card)

    end_at = payload.start_at + timedelta(minutes=service.duration_min)
    appt = crud.create_appointment(db, payload, service, end_at, customer, receipt)

    # Confirmación por WhatsApp (real si Twilio está configurado; simulada si no)
    body = confirmation_message(
        settings.business_name, appt.customer_name, service.name, appt.start_at
    )
    send_whatsapp(appt.customer_phone, body)
    return appt
