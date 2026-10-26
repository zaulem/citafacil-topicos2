"""Tests de cuentas de cliente (US-01): registro, sesión, bloqueo y reservas."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import models
from app.auth import hash_password, verify_password
from app.database import SessionLocal
from app.main import app
from app.utils import local_now, utc_now

client = TestClient(app)

USER = {"email": "Ana@Correo.com", "password": "clave-segura-1", "name": "Ana Pérez", "phone": "6123-4567"}


def _register(**overrides):
    return client.post("/api/auth/register", json={**USER, **overrides})


def _login(email="ana@correo.com", password=USER["password"]):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _next_open_day_at(hour: int):
    d = (local_now() + timedelta(days=1)).replace(hour=hour, minute=0, second=0, microsecond=0)
    while d.weekday() == 6:  # saltar domingo
        d += timedelta(days=1)
    return d


# ---------- Contraseñas ----------
def test_password_hash_roundtrip():
    stored = hash_password("mi-clave-123")
    assert stored.startswith("scrypt$") and "mi-clave-123" not in stored
    assert verify_password("mi-clave-123", stored)
    assert not verify_password("otra-clave", stored)
    assert hash_password("mi-clave-123") != stored  # sal distinta en cada hash
    assert not verify_password("x", "formato-invalido")


# ---------- Registro ----------
def test_register_ok_and_password_not_stored():
    r = _register()
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["token"]
    assert body["customer"] == {"id": body["customer"]["id"], "email": "ana@correo.com",
                                "name": "Ana Pérez", "phone": "+50761234567"}

    db = SessionLocal()
    c = db.query(models.Customer).one()
    assert c.password_hash != USER["password"] and USER["password"] not in c.password_hash
    # el token tampoco se guarda en claro
    assert db.query(models.CustomerSession).one().token_hash != body["token"]
    db.close()


def test_register_duplicate_email():
    assert _register().status_code == 201
    r = _register(email="ANA@correo.com")  # mismo correo con otras mayúsculas
    assert r.status_code == 409


@pytest.mark.parametrize(
    "overrides",
    [
        {"password": "corta"},             # menos de 8 caracteres
        {"email": "no-es-correo"},
        {"phone": "+56 9 4291 6570"},     # no es celular de Panamá
        {"name": "A"},
    ],
)
def test_register_invalid(overrides):
    assert _register(**overrides).status_code == 422


# ---------- Inicio de sesión ----------
def test_login_ok_and_me():
    _register()
    r = _login(email="  ANA@correo.com ")  # se normaliza el correo
    assert r.status_code == 200, r.text
    me = client.get("/api/me", headers=_auth(r.json()["token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "ana@correo.com"


def test_login_wrong_password_and_unknown_email_same_message():
    _register()
    wrong = _login(password="incorrecta-1")
    unknown = _login(email="nadie@correo.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_me_requires_valid_session():
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers=_auth("token-inventado")).status_code == 401


def test_lockout_after_5_failed_attempts():
    _register()
    for _ in range(4):
        assert _login(password="incorrecta-1").status_code == 401
    assert _login(password="incorrecta-1").status_code == 401  # 5.º fallo: bloquea
    r = _login()  # incluso con la contraseña correcta
    assert r.status_code == 423
    assert "bloqueada" in r.json()["detail"]

    # al vencer el bloqueo se puede entrar de nuevo
    db = SessionLocal()
    c = db.query(models.Customer).one()
    c.locked_until = utc_now() - timedelta(seconds=1)
    db.commit()
    db.close()
    assert _login().status_code == 200


def test_successful_login_resets_failed_counter():
    _register()
    for _ in range(4):
        _login(password="incorrecta-1")
    assert _login().status_code == 200
    for _ in range(4):
        assert _login(password="incorrecta-1").status_code == 401  # no se bloquea aún
    assert _login().status_code == 200


# ---------- Sesión ----------
def test_logout_invalidates_token():
    token = _register().json()["token"]
    assert client.post("/api/auth/logout", headers=_auth(token)).status_code == 200
    assert client.get("/api/me", headers=_auth(token)).status_code == 401


def test_expired_session_rejected():
    token = _register().json()["token"]
    db = SessionLocal()
    s = db.query(models.CustomerSession).one()
    s.expires_at = utc_now() - timedelta(seconds=1)
    db.commit()
    db.close()
    assert client.get("/api/me", headers=_auth(token)).status_code == 401


# ---------- Reservas con y sin cuenta ----------
def _book(headers=None, hour=11):
    sid = client.get("/api/services").json()[0]["id"]
    return client.post(
        "/api/appointments",
        headers=headers or {},
        json={"customer_name": "Ana", "customer_phone": "61234567", "service_id": sid,
              "start_at": _next_open_day_at(hour).isoformat()},
    )


def test_booking_with_session_links_customer():
    reg = _register().json()
    r = _book(headers=_auth(reg["token"]))
    assert r.status_code == 201, r.text
    assert r.json()["customer_id"] == reg["customer"]["id"]


def test_guest_booking_still_allowed():
    r = _book()
    assert r.status_code == 201, r.text
    assert r.json()["customer_id"] is None


def test_booking_with_invalid_token_is_guest():
    r = _book(headers=_auth("token-inventado"))
    assert r.status_code == 201
    assert r.json()["customer_id"] is None
