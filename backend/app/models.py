"""Modelos de base de datos (SQLAlchemy)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base
from .utils import utc_now

# Estados posibles de una cita
STATUS_PENDING = "pending"
STATUS_CONFIRMED = "confirmed"
STATUS_CANCELLED = "cancelled"
STATUS_DONE = "done"
VALID_STATUSES = {STATUS_PENDING, STATUS_CONFIRMED, STATUS_CANCELLED, STATUS_DONE}


class Service(Base):
    """Un servicio que ofrece el negocio (ej: Corte de pelo, 30 min, $8.000)."""

    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    duration_min = Column(Integer, nullable=False, default=30)
    price_cents = Column(Integer, nullable=False, default=0)  # USD en centavos (1250 = $12.50)
    active = Column(Boolean, nullable=False, default=True)

    appointments = relationship("Appointment", back_populates="service")


class Appointment(Base):
    """Una reserva/cita hecha por un cliente."""

    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)  # null = invitado
    customer_name = Column(String(120), nullable=False)
    customer_phone = Column(String(20), nullable=False)   # E.164: +5076XXXXXXX
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    start_at = Column(DateTime, nullable=False, index=True)  # hora local (naive)
    end_at = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False, default=STATUS_PENDING)
    notes = Column(String(300), nullable=False, default="")
    reminder_sent = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    service = relationship("Service", back_populates="appointments")
    customer = relationship("Customer", back_populates="appointments")


class Customer(Base):
    """Cliente registrado (US-01). Las reservas de invitados no tienen cliente."""

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(254), nullable=False, unique=True, index=True)  # en minúsculas
    password_hash = Column(String(300), nullable=False)  # scrypt$n$r$p$sal$hash (ver auth.py)
    name = Column(String(120), nullable=False)
    phone = Column(String(20), nullable=False)  # E.164: +5076XXXXXXX
    failed_logins = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True)  # UTC (naive)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    appointments = relationship("Appointment", back_populates="customer")
    sessions = relationship("CustomerSession", back_populates="customer", cascade="all, delete-orphan")


class CustomerSession(Base):
    """Sesión iniciada. Se guarda el SHA-256 del token, nunca el token en claro."""

    __tablename__ = "customer_sessions"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)  # UTC (naive)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    customer = relationship("Customer", back_populates="sessions")
