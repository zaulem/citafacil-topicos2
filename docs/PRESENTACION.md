# Presentación — Proyecto 1 · Tópicos Especiales II

> **Instrucciones para la herramienta de diseño**
> - Cada sección `## Diapositiva N` es **una** diapositiva. Usa el **título** y los **puntos** tal cual; no agregues contenido.
> - Las **Notas del presentador** van en las notas de la diapositiva, **no** en la diapositiva.
> - Donde dice **[Imagen: …]**, deja un espacio para una captura que se agregará después.
> - Estilo sugerido: oscuro y sobrio (fondo `#0d1117`, acentos azul `#3b82f6` y cian `#22d3ee`, ámbar `#f59e0b` para alertas), igual que la app.
> - Los **Anexos** al final **no** son diapositivas: son material de apoyo para el equipo.

---

## Diapositiva 1 — Portada

**CitaFácil: sistema de reservas web con desarrollo asistido por IA**

- Proyecto 1 · Tópicos Especiales II · Prof. Regis Rivera
- Feature Sprint sobre una aplicación existente
- Herramienta de IA: Claude Code (VS Code)

[Imagen: página pública de reservas con el calendario]

**Notas del presentador:** Partimos de una app de reservas real y le agregamos 5 historias de usuario trabajando con IA desde el escritorio. Lo importante no es cuánto código generó la IA, sino cómo la usamos, validamos y corregimos.

---

## Diapositiva 2 — Lo que pedía el proyecto

- Tomar un sistema de reservas existente y evolucionarlo con IA
- **3 historias obligatorias:** pago con datos guardados, calendario dinámico y previsión de demanda
- **Al menos 2 historias propias**
- Demostrar: Git, Issues, commits, ramas, PR, tests, evidencia de IA, errores de la IA, cambios rechazados y decisiones humanas
- Se evalúa **el proceso**, no la herramienta

**Notas del presentador:** El enunciado insiste en analizar el proyecto antes de pedirle código a la IA y en dejar evidencia de cómo se usó. Por eso llevamos una bitácora desde el primer día.

---

## Diapositiva 3 — Repositorio elegido: CitaFácil

| Opción | Por qué no / por qué sí |
|---|---|
| Spring Boot + React | Instalación pesada, sin tests |
| Django + FullCalendar | 3 commits; el calendario ya existía |
| Python + MySQL | 1 commit, login sin terminar |
| **CitaFácil (FastAPI)** ✅ | **Tests con pytest, código modular, instalación simple** |

**Notas del presentador:** Elegimos CitaFácil porque ya traía pruebas automatizadas y un código fácil de entender para todo el equipo; eso permitía analizarlo antes de cambiarlo y hacer cambios en vivo si los piden.

---

## Diapositiva 4 — Cómo trabajamos

- Ciclo por historia: **Issue → rama → commits → Pull Request → QA manual → merge**
- La IA analiza y propone; **un humano decide** y valida en el navegador
- **Bitácora de IA** (`docs/AI_LOG.md`): qué se pidió, qué respondió la IA y qué se decidió
- CI con GitHub Actions: los tests corren solos en cada PR

[Imagen: lista de Pull Requests en GitHub con el check verde]

**Notas del presentador:** Cada cambio pasó por una rama y un PR. La IA nunca hizo cambios sin confirmación: eso quedó como regla después de que configurara algo que no se le pidió (está en la bitácora como cambio rechazado).

---

## Diapositiva 5 — Punto de partida: lo que encontramos

- La app no instalaba en **Python 3.13** → se usó 3.12 (decisión humana: no tocar dependencias)
- **0 de 6 tests** pasaban en Windows (ruta `/tmp` fija)
- El frontend apuntaba siempre a producción
- Bugs del original: resumen de reserva desincronizado, errores ilegibles, solo celulares de Chile
- Vulnerabilidad **XSS** en el panel admin (detectada después en una revisión)

**Notas del presentador:** Antes de agregar funcionalidades hubo que estabilizar la línea base. Varios de estos problemas los encontró la IA al analizar, y otros aparecieron en nuestras pruebas manuales.

---

## Diapositiva 6 — Historias obligatorias

| Historia | Qué se construyó |
|---|---|
| **US-01** Datos de pago guardados | Cuentas con correo y contraseña · pago simulado obligatorio · tarjeta guardada → **pagar con un clic** |
| **US-02** Calendario dinámico | Calendario mensual: horarios libres por día, **pocos cupos en ámbar**, llenos y cerrados · hasta 3 meses |
| **US-03** Previsión de demanda | Panel "Ver Estadísticas": datos reales + interruptor **"Mostrar previsión"** · sugerencias de precio e inventario |

[Imagen: calendario con días en verde y ámbar] [Imagen: paso de pago con "Usar mi tarjeta Visa •••• 4242"]

**Notas del presentador:** La tarjeta guardada solo conserva marca, últimos 4 dígitos y vencimiento, nunca el número completo ni el CVV. La previsión usa el promedio de las últimas 8 semanas con una tendencia amortiguada.

---

## Diapositiva 7 — Historias propias

| Historia | Qué se construyó |
|---|---|
| **US-04** Panamá | Celulares **+507**, zona horaria de Panamá, precios en **USD con centavos** |
| **US-05** Mis reservas | Contadores, filtro por estado, **cancelar con reembolso** y **reprogramar** hasta 24 h antes |

[Imagen: vista "Mis reservas" con contadores y botones Reprogramar / Cancelar]

**Notas del presentador:** US-04 nació de un bug real: el número de Panamá de un integrante era rechazado porque la app solo aceptaba celulares chilenos. US-05 reutiliza el calendario de US-02 para reprogramar.

---

## Diapositiva 8 — La revisión humana cambió el producto

- **"20 vs 21":** con un filtro, un KPI y un gráfico no coincidían → la IA mezclaba datos reales con estimaciones → **datos reales por defecto, previsión aparte y punteada**
- **"Realizada pero reprogramable":** una cita cerrada por el admin seguía editable para el cliente → **reglas de estado únicas** (Realizada y Cancelada son finales)
- **Tabla interminable e histórico excesivo** → caja con desplazamiento, ~300 citas de ejemplo, rango de fechas y filtro por servicio

[Imagen: Ver Estadísticas con "Mostrar previsión" activado]

**Notas del presentador:** Estos cambios no salieron de la IA: salieron de probar la app como usuario y preguntar "¿por qué no cuadra?". La IA ayudó a diagnosticar con los datos de la base, pero la decisión de cómo resolverlo fue nuestra.

---

## Diapositiva 9 — Errores de la IA y cambios rechazados

**Errores (13 documentados), por ejemplo:**
- Un arreglo suyo creó una regresión: tras un error de validación se perdía la hora elegida
- Midió la ocupación en minutos en vez de turnos → nunca detectaba días llenos
- Proyectó la tendencia sin límite → "nadie volverá a pedir Corte niño"
- Mezcló datos reales y estimados en los mismos KPIs

**Rechazados o modificados (11), por ejemplo:** migraciones con Alembic, PIN en lugar de contraseña, selector de 22 países, sub-pestañas para la previsión

**Notas del presentador:** Cada error tiene en la bitácora qué hizo la IA, por qué estaba mal y cómo se corrigió. Varios los detectó la propia IA al revisar sus resultados; otros los encontramos en QA.

---

## Diapositiva 10 — Decisiones humanas clave

- Python 3.12 sin actualizar dependencias · **solo Panamá** · precios con centavos
- Correo + contraseña (solo biblioteca estándar) · invitados pueden reservar
- Calendario propio sin librerías · Chart.js solo para gráficos
- **Datos reales por defecto**, previsión con interruptor
- Cancelada es final · reembolso al cancelar · plazo de 24 h

**51 decisiones** registradas, con la alternativa descartada y su responsable.

**Notas del presentador:** La IA proponía opciones con pros y contras; el equipo elegía. Por ejemplo, rechazamos Alembic para no complicar el proyecto y lo reemplazamos por un procedimiento documentado.

---

## Diapositiva 11 — Calidad y seguridad

- **Tests: de 6 a 108**, verificados en CI en cada PR
- **58 pruebas de QA manual** registradas con resultado
- Seguridad: contraseñas con `scrypt` · sesiones con hash · bloqueo tras 5 intentos · política de contraseña · **XSS corregido** · una reserva ajena no se puede ver ni modificar
- Verificación final: instalación desde cero siguiendo el README y **41/41** comprobaciones de punta a punta

**Notas del presentador:** Varios tests se escribieron para reproducir un bug antes de corregirlo, y comprobamos que fallaran con el código anterior. Así sabemos que de verdad detectan el problema.

---

## Diapositiva 12 — Resultados y aprendizajes

| Métrica | Valor |
|---|---|
| Historias de usuario | 5 (3 obligatorias + 2 propias) |
| Pull Requests · commits | 19 · 60+ |
| Tests automatizados | 108 |
| Hallazgos documentados | 36 |
| Errores de la IA · cambios rechazados · decisiones | 13 · 11 · 51 |

**Aprendizajes:**
- La IA acelera, pero **hay que validar cruzando casos**, no solo el camino feliz
- **Los números deben cuadrar** entre pantallas: la mejor prueba es comparar
- Limitaciones aceptadas: pago simulado, correo sin verificar, sin migraciones

**Notas del presentador:** Cerramos con la demo (ver Anexo A). Si piden un cambio en vivo, el Anexo B dice dónde está cada cosa.

---

# Anexo A — Guion de la demo (≈ 8 minutos)

**Preparación (el día anterior):**
1. En `backend/`: borrar `citafacil.db`, ejecutar `python seed.py` y `python seed_history.py`.
2. Levantar el backend: `python -m uvicorn app.main:app --reload`.
3. Abrir `frontend/index.html` y `frontend/admin.html` (token `cambia-este-token-admin`).

**Recorrido:**
1. **Calendario (US-02):** elegir *Corte + Barba* o *Tinte / Color* → días con número de horarios libres, días con pocos cupos en ámbar, domingo cerrado, avanzar hasta el límite de 3 meses. (Con *Corte de pelo*, que dura menos, puede que ningún día salga en ámbar; revisarlo el día anterior.)
2. **Panamá (US-04):** intentar reservar con `+56 9 1234 5678` → se rechaza con un mensaje claro.
3. **Pago (US-01):** como invitado, pagar con `4242 4242 4242 4242` (12/30, CVV 123); mostrar el rechazo con `4000 0000 0000 0002`.
4. **Cuenta (US-01):** *Crear cuenta* (mostrar la guía de contraseña), reservar marcando *"Guardar tarjeta"*, y en la siguiente reserva **pagar con un clic**.
5. **Mis reservas (US-05):** contadores → **Reprogramar** una cita → **Cancelar** otra (reembolso).
6. **Admin:** tabla con la columna Pago ("Reembolsado"), botones según estado; marcar una cita **Realizada** → en Mis reservas aparece Completada.
7. **Ver Estadísticas (US-03):** mostrar que *Total reservas* coincide con la pestaña Reservas; filtrar por servicio con un clic; **activar "Mostrar previsión"** y comentar las sugerencias.
8. **Proceso:** en GitHub, un Issue → su PR con el check verde → `docs/AI_LOG.md`.

**Datos de prueba:** celular `+507 6XXX XXXX` · contraseña con mayúscula, minúscula y número (ej. `Clave2026`).

---

# Anexo B — Mapa del código (para cambios en vivo)

| Si piden cambiar… | Dónde está |
|---|---|
| Horario de atención, días cerrados, límite de 3 meses, plazo de 24 h | `backend/.env` (`OPEN_HOUR`, `CLOSE_HOUR`, `CLOSED_WEEKDAYS`, `BOOKING_HORIZON_MONTHS`, `CANCEL_MIN_HOURS`) y valores por defecto en `backend/app/config.py` |
| Validación del celular | `backend/app/utils.py` → `normalize_pa_phone` |
| Reglas de tarjeta y tarjeta de prueba rechazada | `backend/app/payments.py` |
| Política de contraseña | Backend: `backend/app/schemas.py` → `CustomerRegister._password_policy` · Guía visual: `frontend/index.html` → `PW_RULES` |
| Intentos de inicio de sesión y bloqueo | `backend/app/config.py` → `login_max_attempts`, `login_lock_minutes` (o agregar `LOGIN_MAX_ATTEMPTS` / `LOGIN_LOCK_MINUTES` al `.env`) |
| Estados de una cita y sus transiciones | `backend/app/models.py` → `ALLOWED_TRANSITIONS` · botones del admin: `frontend/admin.html` → `NEXT_STATUS` |
| Umbral de "pocos cupos" del calendario | `frontend/index.html` → `FEW_SLOTS` |
| Previsión: semanas del modelo, tendencia, umbrales de sugerencias | `backend/app/forecast.py` (constantes al inicio del archivo) |
| Gráficos y KPIs de Ver Estadísticas | `frontend/admin.html` → `renderForecast` |
| Endpoints | Públicos: `backend/app/routers/public.py` · Cuentas y Mis reservas: `routers/accounts.py` · Admin: `routers/admin.py` |
| Mensajes de WhatsApp | `backend/app/notifications.py` |
| Colores del diseño | `:root` al inicio de `frontend/index.html` y `frontend/admin.html` |
| Datos de ejemplo | `backend/seed.py` y `backend/seed_history.py` |

**Para cualquier cambio en vivo:** crear una rama → hacer el cambio → `python -m pytest` en `backend/` (deben pasar los 108) → commit → PR.
