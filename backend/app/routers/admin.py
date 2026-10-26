"""Endpoints de administración (requieren cabecera X-Admin-Token)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..auth import require_admin
from ..availability import max_booking_date
from ..database import get_db
from ..forecast import build_forecast
from ..reminders import run_reminders
from ..utils import add_months, local_now

MAX_RANGE_DAYS = 366  # rango máximo de la vista "Ver Estadísticas"

router = APIRouter(
    prefix="/api/admin",
    tags=["Administración"],
    dependencies=[Depends(require_admin)],
)


# ---------- Servicios ----------
@router.get("/services", response_model=list[schemas.ServiceOut], summary="Listar todos los servicios")
def all_services(db: Session = Depends(get_db)):
    return crud.list_services(db, only_active=False)


@router.post("/services", response_model=schemas.ServiceOut, status_code=201, summary="Crear servicio")
def add_service(payload: schemas.ServiceCreate, db: Session = Depends(get_db)):
    return crud.create_service(db, payload)


@router.put("/services/{service_id}", response_model=schemas.ServiceOut, summary="Editar servicio")
def edit_service(service_id: int, payload: schemas.ServiceUpdate, db: Session = Depends(get_db)):
    service = crud.get_service(db, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Servicio no encontrado.")
    return crud.update_service(db, service, payload)


@router.delete("/services/{service_id}", response_model=schemas.MessageOut, summary="Eliminar servicio")
def remove_service(service_id: int, db: Session = Depends(get_db)):
    service = crud.get_service(db, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Servicio no encontrado.")
    crud.delete_service(db, service)
    return {"detail": "Servicio eliminado."}


# ---------- Citas ----------
@router.get("/appointments", response_model=list[schemas.AppointmentOut], summary="Listar citas")
def all_appointments(
    status: Optional[str] = Query(None, description="Filtrar por estado"),
    day: Optional[date] = Query(None, alias="date", description="Filtrar por fecha YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    return crud.list_appointments(db, status=status, day=day)


@router.patch("/appointments/{appt_id}", response_model=schemas.AppointmentOut, summary="Cambiar estado")
def change_status(appt_id: int, payload: schemas.AppointmentStatusUpdate, db: Session = Depends(get_db)):
    appt = crud.get_appointment(db, appt_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Cita no encontrada.")
    return crud.set_status(db, appt, payload.status)


@router.delete("/appointments/{appt_id}", response_model=schemas.MessageOut, summary="Eliminar cita")
def remove_appointment(appt_id: int, db: Session = Depends(get_db)):
    appt = crud.get_appointment(db, appt_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Cita no encontrada.")
    crud.delete_appointment(db, appt)
    return {"detail": "Cita eliminada."}


# ---------- Estadísticas y recordatorios ----------
@router.get("/stats", response_model=schemas.StatsOut, summary="Estadísticas")
def get_stats(db: Session = Depends(get_db)):
    return crud.stats(db)


@router.get("/forecast", response_model=schemas.ForecastOut, summary="Previsión de demanda (US-03)")
def get_forecast(
    start: Optional[date] = Query(None, description="Desde (YYYY-MM-DD). Por defecto, hace 4 semanas"),
    end: Optional[date] = Query(None, description="Hasta (YYYY-MM-DD). Por defecto, en 1 mes; máximo, el límite de reservas"),
    service_id: Optional[int] = Query(None, description="Filtrar todo por un servicio"),
    db: Session = Depends(get_db),
):
    today = local_now().date()
    start = start or today - timedelta(weeks=4)
    end = end or add_months(today, 1) - timedelta(days=1)
    if end < start:
        raise HTTPException(status_code=422, detail="La fecha 'hasta' debe ser igual o posterior a 'desde'.")
    if end > max_booking_date():
        raise HTTPException(
            status_code=422,
            detail=f"La fecha 'hasta' no puede pasar del {max_booking_date():%d/%m/%Y} (límite de reservas).",
        )
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail="El rango no puede superar un año.")
    service = None
    if service_id is not None:
        service = crud.get_service(db, service_id)
        if not service:
            raise HTTPException(status_code=404, detail="Servicio no encontrado.")
    return build_forecast(db, start, end, service)


@router.post("/reminders/run", summary="Enviar recordatorios ahora")
def trigger_reminders(db: Session = Depends(get_db)):
    return run_reminders(db)
