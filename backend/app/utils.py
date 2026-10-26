"""Utilidades: validación de teléfono panameño y manejo de fechas locales."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .config import settings


class PhoneError(ValueError):
    """Error de validación de número telefónico."""


def normalize_pa_phone(raw: str) -> str:
    """Normaliza un celular panameño a formato E.164 (+5076XXXXXXX).

    Los celulares de Panamá tienen 8 dígitos y empiezan por 6.
    Acepta entradas como:
        "+507 6123 4567", "50761234567", "0050761234567",
        "6123-4567", "61234567"
    """
    digits = re.sub(r"[^\d]", "", raw or "")
    if digits.startswith("00"):          # prefijo internacional 00
        digits = digits[2:]
    if digits.startswith("507"):         # prefijo país
        digits = digits[3:]
    if len(digits) != 8 or not digits.startswith("6"):
        raise PhoneError(
            "Número de celular panameño inválido. Usa el formato +507 6XXX XXXX."
        )
    return "+507" + digits


def utc_now() -> datetime:
    """Hora actual en UTC (naive), para vencimientos de sesión y bloqueos."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_now() -> datetime:
    """Hora actual del negocio (naive, en la zona horaria configurada)."""
    return datetime.now(ZoneInfo(settings.business_timezone)).replace(tzinfo=None)


def to_local_naive(dt: datetime) -> datetime:
    """Convierte un datetime con zona a hora local naive; deja los naive igual."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(ZoneInfo(settings.business_timezone)).replace(tzinfo=None)
    return dt
