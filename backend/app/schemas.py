"""Esquemas Pydantic (validación de entrada/salida de la API)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from .models import VALID_STATUSES
from .payments import CardError, validate_card
from .utils import PhoneError, normalize_pa_phone, to_local_naive


# ---------- Servicios ----------
class ServiceBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    duration_min: int = Field(30, ge=5, le=480)
    price_cents: int = Field(0, ge=0, description="Precio en centavos de USD (1250 = $12.50)")
    active: bool = True


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    duration_min: Optional[int] = Field(None, ge=5, le=480)
    price_cents: Optional[int] = Field(None, ge=0)
    active: Optional[bool] = None


class ServiceOut(ServiceBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- Pago (US-01) ----------
class CardIn(BaseModel):
    number: str = Field(..., examples=["4242 4242 4242 4242"])
    exp_month: int = Field(..., ge=1, le=12)
    exp_year: int = Field(..., ge=0, le=2100, description="AA o AAAA")
    cvv: str = Field(..., examples=["123"])
    brand: Optional[str] = Field(None, exclude=True)  # la calcula el validador

    @model_validator(mode="after")
    def _validate_card(self) -> "CardIn":
        try:
            self.number, self.brand, self.exp_year = validate_card(
                self.number, self.exp_month, self.exp_year, self.cvv
            )
        except CardError as e:
            raise ValueError(str(e))
        return self


class PaymentIn(BaseModel):
    """Una tarjeta nueva (`card`) o la tarjeta guardada (`use_saved_card`)."""

    use_saved_card: bool = False
    card: Optional[CardIn] = None
    save_card: bool = Field(False, description="Guardar `card` en la cuenta (requiere sesión)")

    @model_validator(mode="after")
    def _one_source(self) -> "PaymentIn":
        if self.use_saved_card == (self.card is not None):
            raise ValueError("Indica los datos de una tarjeta o usa tu tarjeta guardada.")
        if self.use_saved_card:
            self.save_card = False
        return self


class CardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    brand: str
    last4: str
    exp_month: int
    exp_year: int


# ---------- Citas ----------
class AppointmentCreate(BaseModel):
    customer_name: str = Field(..., min_length=2, max_length=120)
    customer_phone: str = Field(..., examples=["+507 6123 4567"])
    service_id: int
    start_at: datetime = Field(..., description="Inicio de la cita (ISO 8601)")
    notes: str = Field("", max_length=300)
    payment: PaymentIn

    @field_validator("customer_phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        try:
            return normalize_pa_phone(v)
        except PhoneError as e:
            raise ValueError(str(e))

    @field_validator("start_at")
    @classmethod
    def _naive_local(cls, v: datetime) -> datetime:
        return to_local_naive(v)


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_id: Optional[int] = None
    customer_name: str
    customer_phone: str
    service_id: int
    start_at: datetime
    end_at: datetime
    status: str
    notes: str
    reminder_sent: bool
    payment_status: str
    price_paid_cents: Optional[int] = None
    payment_brand: Optional[str] = None
    payment_last4: Optional[str] = None
    created_at: datetime
    service: Optional[ServiceOut] = None


class AppointmentStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Estado inválido. Debe ser uno de: {sorted(VALID_STATUSES)}")
        return v


# ---------- Cuentas de cliente (US-01) ----------
class CustomerRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=2, max_length=120)
    phone: str = Field(..., examples=["+507 6123 4567"])

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def _password_policy(cls, v: str) -> str:
        """Mínimo 8 caracteres (Field) con al menos una mayúscula, una minúscula y un número."""
        missing = [
            label
            for ok, label in (
                (any(c.isupper() for c in v), "una mayúscula"),
                (any(c.islower() for c in v), "una minúscula"),
                (any(c.isdigit() for c in v), "un número"),
            )
            if not ok
        ]
        if missing:
            raise ValueError("La contraseña debe tener al menos " + ", ".join(missing) + ".")
        return v

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        try:
            return normalize_pa_phone(v)
        except PhoneError as e:
            raise ValueError(str(e))


class CustomerLogin(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=128)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return v.strip().lower()


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str
    phone: str


class SessionOut(BaseModel):
    token: str = Field(..., description="Enviar como cabecera 'Authorization: Bearer <token>'")
    expires_at: datetime
    customer: CustomerOut


# ---------- Calendario mensual ----------
class DayAvailabilityOut(BaseModel):
    date: str
    status: str = Field(..., description="available | full | closed | past | out_of_range")
    free: int = Field(..., description="Horarios libres ese día")


class MonthAvailabilityOut(BaseModel):
    month: str = Field(..., description="YYYY-MM")
    today: str = Field(..., description="Fecha de hoy en la zona horaria del negocio")
    max_date: str = Field(..., description="Último día reservable")
    days: list[DayAvailabilityOut]


# ---------- Estadísticas reales y previsión (US-03, #20, H-28) ----------
class Occupancy(BaseModel):
    occupancy_pct: Optional[float] = None
    level: str = Field(..., description="high | low | normal, comparado con el promedio del negocio")


class WeekdayOccupancy(Occupancy):
    weekday: str


class HourOccupancy(Occupancy):
    hour: str


class ServiceRevenue(BaseModel):
    service_id: int
    service: str
    appointments: int = Field(..., description="Citas registradas (realizadas + reservadas)")
    revenue_cents: int


class Suggestion(BaseModel):
    level: str = Field(..., description="high | low | info")
    text: str


class RealKpis(BaseModel):
    total: int = Field(..., description="Todas las citas del rango, incluidas las canceladas")
    registered: int = Field(..., description="Citas no canceladas (= realizadas + reservadas)")
    done: int = Field(..., description="Registradas en días pasados")
    booked: int = Field(..., description="Registradas desde hoy (reservas futuras)")
    cancelled: int
    cancellation_rate_pct: float = Field(..., description="Canceladas / total")
    revenue_cents: int = Field(..., description="Cobrado: realizadas + reservadas (el pago es por adelantado)")
    avg_ticket_cents: int
    occupancy_pct: float


class RealWeek(BaseModel):
    week_start: str
    done: int
    booked: int
    cancelled: int


class RealSection(BaseModel):
    basis: str = Field(..., description="done | booked: qué citas miden la ocupación")
    kpis: RealKpis
    weekly: list[RealWeek]
    by_weekday: list[WeekdayOccupancy]
    by_hour: list[HourOccupancy]
    by_service: list[ServiceRevenue]
    suggestions: list[Suggestion]


class ForecastKpis(BaseModel):
    expected: float = Field(..., description="Citas estimadas desde hoy hasta el fin del rango (incluye las reservadas)")
    booked: int = Field(..., description="Ya reservadas en esos días")
    additional: float = Field(..., description="Estimadas que aún no se han reservado")
    additional_revenue_cents: int
    occupancy_pct: float
    trend_pct_per_week: float


class ForecastWeek(BaseModel):
    week_start: str
    expected: float
    booked: int
    additional: float


class ForecastDay(BaseModel):
    date: str
    expected: float
    booked: int
    occupancy_pct: float


class ForecastSection(BaseModel):
    available: bool = Field(..., description="False si el rango termina antes de hoy")
    kpis: ForecastKpis
    weekly: list[ForecastWeek]
    daily: list[ForecastDay]
    by_weekday: list[WeekdayOccupancy]
    suggestions: list[Suggestion]


class ServiceRef(BaseModel):
    id: int
    name: str


class ForecastOut(BaseModel):
    start: str
    end: str
    today: str
    max_date: str = Field(..., description="Último día que se puede consultar (límite de reservas)")
    service: Optional[ServiceRef] = None
    real: RealSection
    forecast: ForecastSection


# ---------- Otros ----------
class ConfigOut(BaseModel):
    business_name: str
    timezone: str
    currency: str
    open_hour: int
    close_hour: int
    slot_interval_minutes: int
    closed_weekdays: list[int]


class StatsOut(BaseModel):
    total: int
    pending: int
    confirmed: int
    cancelled: int
    done: int
    upcoming: int


class MessageOut(BaseModel):
    detail: str
