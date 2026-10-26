"""Pago simulado (US-01): validación de tarjetas y cobro ficticio.

No hay pasarela real ni se mueve dinero. Del número de tarjeta solo se conservan
la marca y los últimos 4 dígitos; el número completo y el CVV nunca se guardan.

Tarjetas de prueba:
    4242 4242 4242 4242  -> aprobada (Visa)
    4000 0000 0000 0002  -> rechazada por el "banco" (PaymentDeclined)
"""
from __future__ import annotations

import re
from typing import Optional

from . import models
from .utils import local_now

DECLINED_TEST_CARD = "4000000000000002"


class CardError(ValueError):
    """Datos de tarjeta inválidos."""


class PaymentDeclined(Exception):
    """El cobro fue rechazado."""


def luhn_ok(number: str) -> bool:
    """Algoritmo de Luhn: detecta errores de tipeo en el número de tarjeta."""
    total = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def card_brand(number: str) -> Optional[str]:
    """Marca según los primeros dígitos y el largo; None si no se reconoce."""
    if re.match(r"^3[47]", number) and len(number) == 15:
        return "Amex"
    if number.startswith("4") and len(number) in (13, 16, 19):
        return "Visa"
    if len(number) == 16 and (51 <= int(number[:2]) <= 55 or 2221 <= int(number[:4]) <= 2720):
        return "Mastercard"
    return None


def validate_card(number: str, exp_month: int, exp_year: int, cvv: str) -> tuple[str, str, int]:
    """Valida la tarjeta y devuelve (número solo dígitos, marca, año en 4 dígitos)."""
    digits = re.sub(r"[\s-]", "", number or "")
    if not digits.isdigit():
        raise CardError("El número de tarjeta solo puede tener dígitos.")
    brand = card_brand(digits)
    if not brand:
        raise CardError("Tarjeta no reconocida. Aceptamos Visa, Mastercard y Amex.")
    if not luhn_ok(digits):
        raise CardError("Número de tarjeta inválido. Revisa los dígitos.")

    year = exp_year + 2000 if exp_year < 100 else exp_year
    today = local_now().date()
    if (year, exp_month) < (today.year, today.month):
        raise CardError("La tarjeta está vencida.")

    cvv_len = 4 if brand == "Amex" else 3
    if not (cvv or "").isdigit() or len(cvv) != cvv_len:
        raise CardError(f"El código de seguridad (CVV) debe tener {cvv_len} dígitos.")
    return digits, brand, year


def charge(
    amount_cents: int,
    *,
    number: Optional[str] = None,
    saved: Optional[models.PaymentMethod] = None,
) -> dict:
    """Cobro simulado. Devuelve el comprobante {brand, last4} o lanza PaymentDeclined."""
    if saved is not None:
        return {"brand": saved.brand, "last4": saved.last4}
    if number == DECLINED_TEST_CARD:
        raise PaymentDeclined("Pago rechazado por el banco. Prueba con otra tarjeta.")
    return {"brand": card_brand(number), "last4": number[-4:]}
