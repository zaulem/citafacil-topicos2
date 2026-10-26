"""Cuentas de cliente (US-01): registro, inicio/cierre de sesión y datos propios.

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
from ..config import settings
from ..database import get_db
from ..utils import utc_now

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
