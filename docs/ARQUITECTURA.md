# Análisis de arquitectura — CitaFácil

Fecha: 2026-10-25 · Elaborado con Claude Code (solo lectura) y revisado por el equipo.
Decisiones y hallazgos referenciados en [AI_LOG.md](AI_LOG.md).

## 1. Arquitectura actual

```
frontend/index.html  ──┐                       ┌─ routers/public.py  → config, servicios, disponibilidad, crear cita
frontend/admin.html  ──┼── fetch → FastAPI ────┼─ routers/admin.py   → CRUD servicios/citas, estado, stats (token)
                       │   (app/main.py)       └─ routers/scores.py  → ranking de un videojuego (H-11, se elimina)
                       │        │
                       │   crud.py · availability.py · utils.py · notifications.py · reminders.py
                       │        │
                       └── SQLAlchemy → SQLite (local) / PostgreSQL (prod): services, appointments, game_scores
```

| Aspecto | Estado actual |
|---|---|
| Modelo de datos | `Service` y `Appointment`. No existe "cliente": nombre y teléfono se guardan como texto en cada cita |
| Disponibilidad | Un solo recurso (un barbero): el solapamiento se valida contra todas las citas del día |
| Autenticación | Solo admin, con un token compartido (`X-Admin-Token`). Sin usuarios |
| Pagos | No existen |
| Localización | Chile: teléfonos +56, `America/Santiago`, CLP como entero |
| Migraciones | No hay; `create_all()` al iniciar |
| Tests | `backend/tests/test_booking.py` (6 tests, pytest) |

## 2. Hallazgos del análisis

| ID | Hallazgo | Tratamiento |
|---|---|---|
| H-11 | Router `scores.py` ajeno al dominio, con POST público sin autenticación | Eliminar |
| H-12 | Fecha mínima en UTC (`toISOString()`): en Panamá desde las 19:00 no se puede reservar para hoy | Resuelto en US-02 |
| H-13 | "Ahora" se calcula en hora de Santiago (2 h adelante de Panamá) | Resuelto en US-04 |
| H-14 | Sin migraciones: no se agregan columnas a tablas existentes | Recrear la BD local (ver §5) |
| H-15 | La cita no guarda el precio cobrado | `price_paid` en US-01 |

## 3. Historias de usuario e impacto

### US-01 · Reservar con datos de pago guardados (obligatoria)

Se divide en dos PRs: **A** (cuentas de cliente) y **B** (pago simulado y tarjeta guardada).
> Como usuario recurrente, quiero reservar directamente usando mis datos guardados, para no tener que rellenar el formulario de pago en cada compra.

- **Backend:** tablas `Customer` (correo, hash de contraseña, nombre, celular), `CustomerSession` (token con vencimiento) y `PaymentMethod` (solo marca, últimos 4 dígitos, vencimiento y token simulado; **nunca el número completo**). `Appointment` recibe `customer_id`, `price_paid` y `payment_status`. Endpoints de registro, login, perfil y tarjeta, y pago simulado al reservar.
- **Sesiones:** token aleatorio entregado al cliente; en la BD solo se guarda su SHA-256. Cabecera `Authorization: Bearer <token>`, vigencia de 7 días.
- **Seguridad (solo biblioteca estándar):** `hashlib.scrypt` con sal por usuario, `secrets.token_urlsafe` para sesiones, bloqueo temporal tras 5 intentos fallidos y contraseña de mínimo 8 caracteres. El correo se valida con `email-validator`, que ya instala FastAPI.
- **Limitación conocida:** el correo no se verifica (no se envían correos).
- **Frontend:** registro e inicio de sesión; paso de pago con la opción "usar mi tarjeta •••• 4242".

### US-02 · Calendario dinámico (obligatoria)
> Como cliente, quiero ver un calendario dinámico con los días disponibles y ocupados, para elegir mi fecha rápidamente sin intentos fallidos.

- **Backend:** `GET /api/availability/month?service_id=&month=YYYY-MM`, que devuelve cada día como disponible, lleno, cerrado o pasado, reutilizando `generate_slots()`.
- **Frontend:** grilla mensual con colores en lugar del campo de fecha. Corrige H-12.

### US-03 · Previsión de demanda (obligatoria)
> Como administrador del sistema, quiero ver gráficos de previsión de la demanda basados en el histórico, para ajustar los precios y el inventario de forma inteligente.

- **Backend:** `GET /api/admin/forecast`, que agrega el histórico por día de la semana, franja horaria y servicio, y proyecta las próximas semanas con media móvil más estacionalidad semanal, sin librerías nuevas.
- **Datos:** script `seed_history.py` con unos 6 meses de citas.
- **Frontend:** Chart.js por CDN en `admin.html`.

### US-04 · Teléfonos y localización de Panamá (propia)
> Como cliente en Panamá, quiero registrar mi celular con formato +507, para recibir la confirmación de mi reserva en mi WhatsApp local.

- Reemplazar la validación chilena por la panameña: `+507` más 8 dígitos, celular que empieza por 6, guardado en E.164.
- `.env` y valores por defecto: `America/Panama` (corrige H-13) y moneda USD.
- **Decidido:** precios en USD con centavos (p. ej. 12.50).

### US-05 · Mis reservas (propia)
> Como cliente registrado, quiero ver y cancelar mis reservas desde mi cuenta, para gestionar cambios sin tener que llamar al negocio.

- Depende de US-01. **Por decidir:** si se puede cancelar en cualquier momento o solo hasta X horas antes.

## 4. Orden de trabajo

| # | Rama | Contenido | Depende de |
|---|---|---|---|
| 1 | `chore/eliminar-router-juego` | H-11 | — |
| 2 | `feature/US-04-panama` | Teléfonos +507, zona horaria, moneda | — |
| 3 | `feature/US-02-calendario` | Calendario mensual | — |
| 4 | `feature/US-01-datos-guardados` | Cuentas, tarjeta guardada, pago simulado | US-04 |
| 5 | `feature/US-05-mis-reservas` | Ver y cancelar reservas | US-01 |
| 6 | `feature/US-03-prevision` | Previsión de demanda (puede ir en paralelo) | — |

## 5. Procedimiento cuando cambia el modelo de datos (sin migraciones)

```
cd backend
del citafacil.db                       # PowerShell: Remove-Item citafacil.db
$env:PYTHONUTF8=1; python seed.py      # PYTHONUTF8 evita el error de H-04
```
Al iniciar, el backend vuelve a crear las tablas con `create_all()`.

**Configuración local (`backend/.env`, no se sube a GitHub):** desde US-04 debe contener
```
BUSINESS_TIMEZONE=America/Panama
CURRENCY=USD
```
El `.env` tiene prioridad sobre los valores del código (H-17). Quien lo creó antes de US-04 debe actualizarlo o volver a copiarlo desde `.env.example`.
