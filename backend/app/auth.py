"""Autenticación: token de administración y cuentas de cliente (US-01).

Las cuentas de cliente usan solo la biblioteca estándar:
- Contraseñas con `hashlib.scrypt` y una sal aleatoria por cliente.
- Sesiones con un token aleatorio (`secrets`); en la BD se guarda su SHA-256.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .database import get_db
from .utils import utc_now

# Parámetros de scrypt (costo de CPU/memoria). Se guardan junto al hash para
# poder subirlos en el futuro sin invalidar las contraseñas existentes.
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def require_admin(x_admin_token: str = Header(..., alias="X-Admin-Token")) -> None:
    """Valida la cabecera X-Admin-Token contra el token configurado."""
    if x_admin_token != settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de administrador inválido.",
        )


# ---------- Contraseñas ----------
def hash_password(password: str) -> str:
    """Devuelve 'scrypt$n$r$p$sal_hex$hash_hex'."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=64
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_hex, hash_hex = stored.split("$")
        if algo != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(hash_hex) // 2,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), hash_hex)  # comparación en tiempo constante


# ---------- Sesiones ----------
def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, customer: models.Customer) -> tuple[str, models.CustomerSession]:
    """Crea una sesión y devuelve el token en claro (solo se entrega una vez)."""
    token = secrets.token_urlsafe(32)
    session = models.CustomerSession(
        customer_id=customer.id,
        token_hash=_token_hash(token),
        expires_at=utc_now() + timedelta(days=settings.session_days),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return token, session


def _bearer_token(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


def _session_for(db: Session, token: Optional[str]) -> Optional[models.CustomerSession]:
    if not token:
        return None
    session = (
        db.query(models.CustomerSession)
        .filter(models.CustomerSession.token_hash == _token_hash(token))
        .first()
    )
    if not session or session.expires_at <= utc_now():
        return None
    return session


def optional_customer(
    authorization: Optional[str] = Header(None), db: Session = Depends(get_db)
) -> Optional[models.Customer]:
    """Cliente de la sesión, o None si no hay sesión válida (reserva como invitado)."""
    session = _session_for(db, _bearer_token(authorization))
    return session.customer if session else None


def require_session(
    authorization: Optional[str] = Header(None), db: Session = Depends(get_db)
) -> models.CustomerSession:
    """Exige una sesión válida (cabecera `Authorization: Bearer <token>`)."""
    session = _session_for(db, _bearer_token(authorization))
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o vencida. Inicia sesión de nuevo.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return session
