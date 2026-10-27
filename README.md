# 📅 CitaFácil — Sistema de reservas web (Proyecto 1 · Tópicos Especiales II)

[![Tests](https://github.com/zaulem/citafacil-topicos2/actions/workflows/tests.yml/badge.svg)](https://github.com/zaulem/citafacil-topicos2/actions/workflows/tests.yml)

Sistema de reservas para una barbería en **Panamá**: los clientes reservan y pagan en línea, gestionan sus citas desde su cuenta, y el administrador ve estadísticas reales y una previsión de la demanda.

Este repositorio parte de **[CitaFácil](https://github.com/gianca675/citafacil)**, de Giancarlos Alfaro, y lo extiende como *Feature Sprint* con desarrollo asistido por IA (Claude Code) para el **Proyecto 1 de Tópicos Especiales II** (Prof. Regis Rivera).

- 📒 **Bitácora de IA, hallazgos, decisiones y QA:** [`docs/AI_LOG.md`](docs/AI_LOG.md)
- 🧭 **Análisis de arquitectura y decisiones de diseño:** [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md)

---

## ✅ Historias de usuario implementadas

| Historia | Issue | Qué se puede hacer |
|---|---|---|
| **US-01** · Reservar con datos de pago guardados *(obligatoria)* | #10 | Cuenta con correo y contraseña; pago simulado obligatorio; tarjeta guardada para pagar con un clic |
| **US-02** · Calendario dinámico *(obligatoria)* | #9 | Calendario mensual con días disponibles, con pocos cupos, llenos y cerrados; reservas hasta 3 meses adelante |
| **US-03** · Previsión de demanda *(obligatoria)* | #12, #20 | Panel "Ver Estadísticas" con datos reales y, al activar **"Mostrar previsión"**, la previsión de demanda y sugerencias de precio e inventario |
| **US-04** · Celulares y localización de Panamá *(propia)* | #8 | Celulares +507, zona horaria `America/Panama`, precios en USD con centavos |
| **US-05** · Mis reservas *(propia)* | #11 | Ver, cancelar (con reembolso) y reprogramar las reservas propias |

---

## ✨ Características

**Página pública** (`frontend/index.html`)
- Reserva en 3 pasos: servicio → día en el **calendario** → hora libre.
- **Pago simulado** obligatorio, con validación de tarjeta: regla de Luhn, marca, vencimiento y CVV.
- **Cuenta de cliente:** registro e inicio de sesión. Con sesión, los datos se precargan y la tarjeta guardada permite pagar con un clic.
- **Mis reservas:** contadores (total, programadas, completadas, canceladas), filtro por estado, **cancelar con reembolso** y **reprogramar** hasta 24 h antes.

**Panel de administración** (`frontend/admin.html`, protegido por token)
- **Reservas:** tabla con desplazamiento propio, filtros, columna de pago (pagado o reembolsado) y acciones válidas según el estado de cada cita.
- **Servicios:** crear, activar o desactivar y eliminar.
- **Ver Estadísticas:**
  - Rango de fechas y filtro cruzado por servicio (clic en un gráfico).
  - KPIs que cuadran con la pestaña Reservas.
  - Gráficos con Chart.js.
  - Interruptor **"Mostrar previsión"**: la estimación aparece separada y con estilo punteado, sin mezclarse con los datos reales.

**Reglas de negocio**
- Estados de una cita: Pendiente → Confirmada → Realizada; cualquiera de las dos primeras puede pasar a Cancelada. **Realizada y Cancelada son finales.**
- Sin doble reserva: la disponibilidad tiene en cuenta la duración de cada servicio.
- Recordatorios por WhatsApp con Twilio. Sin credenciales funciona en **modo demo** (los mensajes se registran en el log).

---

## 🧱 Stack técnico

| Capa | Tecnología |
|---|---|
| Backend | Python **3.12**, FastAPI, SQLAlchemy, Pydantic, APScheduler |
| Seguridad | `hashlib.scrypt` (contraseñas), `secrets` (sesiones), solo biblioteca estándar |
| Base de datos | SQLite (local) · PostgreSQL (producción) |
| Frontend | HTML, CSS y JavaScript sin framework · Chart.js 4.4.1 (CDN) |
| Tests | pytest (108 tests) · GitHub Actions (CI) |
| Despliegue | Docker · Render |

---

## 📂 Estructura

```
├── .github/workflows/tests.yml   # CI: ejecuta los tests en cada push y Pull Request
├── backend/
│   ├── app/
│   │   ├── main.py               # App FastAPI, CORS, programador de recordatorios
│   │   ├── config.py             # Configuración por variables de entorno
│   │   ├── models.py             # Servicio, Cita, Cliente, Sesión, Tarjeta + reglas de estado
│   │   ├── schemas.py            # Validación (Pydantic)
│   │   ├── crud.py               # Operaciones de base de datos
│   │   ├── availability.py       # Horarios libres, calendario mensual, anti doble reserva
│   │   ├── payments.py           # Pago simulado y validación de tarjetas
│   │   ├── forecast.py           # Estadísticas reales y previsión de demanda
│   │   ├── auth.py               # Token de admin, contraseñas y sesiones de cliente
│   │   ├── notifications.py      # WhatsApp (Twilio o modo demo)
│   │   ├── reminders.py          # Recordatorios automáticos
│   │   └── routers/              # public · accounts (cuentas y mis reservas) · admin
│   ├── tests/                    # 108 tests (conftest.py fija la configuración de prueba)
│   ├── seed.py                   # Servicios y citas de ejemplo
│   ├── seed_history.py           # ~300 citas en 3 meses para "Ver Estadísticas"
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html                # Página pública: reservar y mis reservas
│   └── admin.html                # Panel de administración
└── docs/
    ├── AI_LOG.md                 # Bitácora de IA (entregable)
    └── ARQUITECTURA.md           # Análisis y decisiones de diseño
```

---

## 🖥️ Ejecutar en local (Windows · PowerShell)

Requisito: **Python 3.12**. Las versiones fijadas en `requirements.txt` no se instalan en Python 3.13; está documentado como hallazgo H-01.

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env            # ajusta ADMIN_TOKEN si quieres
python seed.py                    # servicios y citas de ejemplo
python seed_history.py            # opcional: histórico para "Ver Estadísticas"
python -m uvicorn app.main:app --reload
```

- **API y documentación:** <http://localhost:8000/docs>
- **Página pública:** abre `frontend/index.html` (doble clic o Live Server). En local usa `http://localhost:8000` automáticamente.
- **Panel admin:** `frontend/admin.html`, con el `ADMIN_TOKEN` del `.env` (por defecto `cambia-este-token-admin`).

> **Si cambia el modelo de datos:** el proyecto no usa migraciones (decisión documentada en H-14). Borra `backend/citafacil.db` y vuelve a ejecutar `seed.py` (y `seed_history.py`).

### Datos de prueba
| Qué | Valor |
|---|---|
| Tarjeta aprobada | `4242 4242 4242 4242` · vencimiento futuro (ej. `12/30`) · CVV `123` |
| Tarjeta rechazada | `4000 0000 0000 0002` |
| Celular | Panamá: `+507 6XXX XXXX` (8 dígitos que empiezan por 6) |
| Contraseña al crear cuenta | 8 caracteres o más, con mayúscula, minúscula y número |

---

## 🔌 Endpoints principales

| Método | Ruta | Descripción | Auth |
|---|---|---|---|
| GET | `/api/services` · `/api/config` | Servicios activos y datos del negocio | — |
| GET | `/api/availability?service_id=&date=` | Horarios libres de un día | — |
| GET | `/api/availability/month?service_id=&month=` | Estado de cada día del mes (calendario) | — |
| POST | `/api/appointments` | Crear una reserva con pago | — / 👤 |
| POST | `/api/auth/register` · `/login` · `/logout` | Cuenta de cliente | — / 👤 |
| GET | `/api/me` · `/api/me/card` (PUT, DELETE) | Mis datos y tarjeta guardada | 👤 |
| GET | `/api/me/appointments` | Mis reservas con contadores | 👤 |
| POST | `/api/me/appointments/{id}/cancel` · `/reschedule` | Cancelar (reembolso) o reprogramar | 👤 |
| GET · PATCH · DELETE | `/api/admin/appointments` | Listar, cambiar estado y eliminar | 🔒 |
| GET/POST/PUT/DELETE | `/api/admin/services` | Gestionar servicios | 🔒 |
| GET | `/api/admin/stats` | Contadores de la pestaña Reservas | 🔒 |
| GET | `/api/admin/forecast?start=&end=&service_id=` | Estadísticas reales y previsión | 🔒 |

👤 = sesión de cliente (`Authorization: Bearer <token>`) · 🔒 = cabecera `X-Admin-Token`.

---

## ⚙️ Configuración (variables de entorno)

| Variable | Por defecto | Descripción |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./citafacil.db` | Conexión a la base de datos |
| `ADMIN_TOKEN` | `cambia-este-token-admin` | Token del panel admin |
| `BUSINESS_NAME` | `Barbería Don Lucho` | Nombre del negocio |
| `BUSINESS_TIMEZONE` / `CURRENCY` | `America/Panama` / `USD` | Localización |
| `OPEN_HOUR` / `CLOSE_HOUR` | `10` / `20` | Horario de atención |
| `SLOT_INTERVAL_MINUTES` | `30` | Separación entre horarios |
| `CLOSED_WEEKDAYS` | `6` | Días cerrados (0 = lunes … 6 = domingo) |
| `BOOKING_HORIZON_MONTHS` | `3` | Hasta cuántos meses adelante se puede reservar |
| `CANCEL_MIN_HOURS` | `24` | Hasta cuántas horas antes se puede cancelar o reprogramar |
| `SESSION_DAYS` | `7` | Duración de la sesión del cliente |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_LOCK_MINUTES` | `5` / `15` | Bloqueo tras intentos fallidos |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_WHATSAPP_FROM` | — | WhatsApp real (vacío = modo demo) |
| `REMINDER_HOURS_BEFORE` | `24` | Horas antes para el recordatorio |

---

## 🧪 Tests

```powershell
cd backend
python -m pytest
```

**108 tests:**
- Reservas y disponibilidad, calendario y límite de 3 meses.
- Cuentas, sesiones y bloqueo.
- Pago y tarjeta guardada.
- Estadísticas, previsión y conciliación con la pestaña Reservas.
- Mis reservas, reglas de estado entre admin y cliente, y XSS en el panel admin.

Los tests fijan su propia configuración (`tests/conftest.py`), así que no dependen del `.env` de cada integrante. Se ejecutan automáticamente en GitHub Actions en cada push a `main` y en cada Pull Request.

---

## 🤖 Proceso y uso de IA

El desarrollo se hizo con **Claude Code** (Claude Opus) desde VS Code, con el ciclo: Issue → rama → commits → Pull Request → QA manual → merge.

Todo lo relevante está en [`docs/AI_LOG.md`](docs/AI_LOG.md):
- **AI Development Log:** qué se le pidió a la IA, qué devolvió y qué se decidió.
- **Hallazgos (H-01 a H-35):** bugs del proyecto original, errores de la IA y limitaciones.
- **Respuestas incorrectas de la IA**, **cambios rechazados o modificados** y **decisiones humanas**.
- **Pruebas automatizadas y pruebas manuales de QA.**

---

## ⚠️ Limitaciones conocidas

- El **pago es simulado**: no hay pasarela real. Solo se guardan la marca y los últimos 4 dígitos de la tarjeta.
- **No se verifica** que el correo pertenezca al cliente, porque la app no envía correos (H-20).
- **Sin migraciones:** al cambiar el modelo hay que recrear la base local (H-14).
- La **previsión** es una estimación simple: promedio de 8 semanas con tendencia amortiguada. No son citas reservadas.

---

## ☁️ Desplegar en Render

`render.yaml` crea la API y una base PostgreSQL (**New + → Blueprint** en [Render](https://render.com)). Después hay que abrir el frontend con `?api=https://tu-api.onrender.com`, o usar el enlace **"Configurar API"** del pie de página.

---

## 👤 Créditos

- Proyecto original: **Giancarlos Alfaro** ([GitHub](https://github.com/gianca675) · [Portafolio](https://gianca675.github.io)), licencia MIT.
- Extensión para el Proyecto 1 de Tópicos Especiales II: equipo del curso, con desarrollo asistido por IA.

Licencia MIT.
