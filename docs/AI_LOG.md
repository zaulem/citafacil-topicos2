# Bitácora de desarrollo asistido por IA — CitaFácil

Proyecto 1 · Tópicos Especiales II · Prof. Regis Rivera
Repositorio base: [gianca675/citafacil](https://github.com/gianca675/citafacil) · Repositorio del grupo: [zaulem/citafacil-topicos2](https://github.com/zaulem/citafacil-topicos2)

Este documento se actualiza en cada PR. Solo se registran los prompts que afectaron de forma significativa el desarrollo.

**Herramientas IA usadas**

| Herramienta | Modelo | Uso principal |
|---|---|---|
| Claude Code (extensión VS Code) | Claude Opus 5.5 | Análisis, setup, código, tests, diagnóstico |

---

## 1. AI Development Log

| # | Fecha | Actividad | Herramienta IA | Qué se solicitó | Resultado | Decisión humana | Ref. |
|---|---|---|---|---|---|---|---|
| 1 | 2026-10-25 | Análisis | Claude Code | Analizar el enunciado y comparar los 4 repositorios | Revisó los 4 repos en GitHub; recomendó CitaFácil (tests con pytest, setup simple, código modular) | Aceptada: se elige CitaFácil | — |
| 2 | 2026-10-25 | Setup | Claude Code | Clonar y publicar en repo propio | Clonó, renombró el remoto original a `upstream`; el push falló por falta de autenticación | Se hizo el push manualmente desde la terminal del usuario | H-00 |
| 3 | 2026-10-25 | Setup | Claude Code | Instalar dependencias y correr tests | Detectó que las versiones fijadas no instalan en Python 3.13 | Usar Python 3.12 en lugar de actualizar dependencias | H-01 |
| 4 | 2026-10-25 | Testing / Debug | Claude Code | Correr línea base de tests | 6/6 tests en error; diagnosticó ruta `/tmp` fija y propuso `tempfile.gettempdir()` | Aceptada sin cambios | H-02, PR #1 |
| 5 | 2026-10-25 | Código | Claude Code | Hacer que el frontend use el backend local | Detección automática de entorno local; producción por defecto | Aceptada | H-03, PR #2 |
| 6 | 2026-10-25 | Debug | Claude Code | Analizar error "Elige servicio, día y hora" visto al probar | Encontró 2 bugs del original (resumen desincronizado, errores 422 ilegibles) y la restricción de teléfonos chilenos | Corregir bugs ahora; el teléfono se convierte en historia de usuario | H-05, H-06, H-07 |
| 7 | 2026-10-25 | Configuración | Claude Code | Pregunta: ¿está bien usar Live Server? | Respondió y además creó `.vscode/settings.json` sin que se lo pidieran | Rechazado: se eliminó el archivo y se fijó la regla de confirmar antes de cualquier cambio | H-09 |
| 8 | 2026-10-25 | Debug | Claude Code | Analizar captura de QA: tras error de teléfono el formulario queda desactivado | Identificó que su propio arreglo de H-05 borraba la hora en cualquier error; propuso recargar horarios solo en 409 | Aceptado tras confirmación | H-10 |
| 9 | 2026-10-25 | Arquitectura | Claude Code | Analizar la arquitectura para las 3 historias obligatorias + 2 propias (solo lectura) | Mapa de capas, impacto por historia, 5 hallazgos nuevos (H-11–H-15), orden sugerido y texto de Issues ([ARQUITECTURA.md](ARQUITECTURA.md)) | Aceptado parcialmente: se rechazó Alembic, se redujo US-04 a solo Panamá y se cambió el login de teléfono + PIN a correo + contraseña | H-11–H-15 |
| 10 | 2026-10-25 | Código | Claude Code | Eliminar el router del videojuego (H-11) | Borró `scores.py` y sus referencias; 6/6 tests OK; `/api/scores` ya no aparece en las rutas | Aceptado | H-11 |
| 11 | 2026-10-25 | Código / Testing | Claude Code | Implementar US-04 (#8) según plan aprobado: teléfonos +507, `America/Panama`, USD en centavos | Cambios en backend, frontend, seed y config; tests de 6 a 14. Un test falló por el `.env` local con valores de Chile | Aceptado; la IA corrigió el `.env` local con autorización | H-07, H-13, H-16, H-17 |
| 12 | 2026-10-25 | Testing | Claude Code | Aislar los tests del `.env` local (H-18, opción B) | Reprodujo el fallo simulando la configuración de otro integrante (3/14 fallaban) y fijó la configuración en los tests: 14/14 en ambos casos | Aceptado | H-18 |
| 13 | 2026-10-25 | Código / Testing | Claude Code | Implementar US-02 (#9) según plan aprobado: calendario mensual propio, nº de horarios libres por día, aviso de pocos cupos y límite de 3 meses | Endpoint mensual, calendario en JS puro (sin librerías) y 9 tests nuevos (23/23). Un primer intento de edición del HTML falló por un error de comillas del shell y no modificó nada; se rehízo con la herramienta de edición | Aceptado; QA aprobado (QA-09 a QA-13), PR #15 | H-12 |
| 14 | 2026-10-26 | Código / Testing | Claude Code | Implementar US-01 parte A (#10): cuentas de cliente con correo y contraseña, solo biblioteca estándar | Registro, login con bloqueo tras 5 intentos, logout, `/api/me`, reservas asociadas al cliente y frontend con ventana de acceso; 17 tests nuevos (40/40). Detectó el riesgo H-19 al separar los tests y lo resolvió con `conftest.py`. Evitó insertar el nombre del cliente como HTML | Aceptado; pendiente QA manual | H-19, H-20, H-21 |

---

## 2. Incidencias y hallazgos

| ID | Fecha | Tipo | Descripción | Cómo se detectó | Resolución | Estado |
|---|---|---|---|---|---|---|
| H-00 | 2026-10-25 | Entorno | El agente IA no puede autenticarse en GitHub de forma interactiva | Primer `git push` desde la IA | Login con Git Credential Manager desde la terminal; luego la IA puede hacer push | Resuelto |
| H-01 | 2026-10-25 | Entorno | `psycopg2-binary==2.9.9` y `pydantic==2.7.4` (→ `pydantic-core==2.18.4`) no tienen binarios para Python 3.13 | `pip install` fallido | Instalar Python 3.12 (coincide con `render.yaml`) | Resuelto |
| H-02 | 2026-10-25 | Bug (original) | Los tests usan `sqlite:////tmp/...`; en Windows `C:\tmp` no existe → 6 tests en error | `pytest` línea base | `tempfile.gettempdir()` en `backend/tests/test_booking.py` | Resuelto (PR #1) |
| H-03 | 2026-10-25 | Configuración | El frontend apuntaba siempre a la API de producción en Render | Revisión de código | Usa `http://localhost:8000` si se abre en local | Resuelto (PR #2) |
| H-04 | 2026-10-25 | Bug (original) | `seed.py` falla en consolas Windows (cp1252) al imprimir "✔"; solo se guardan los servicios | Ejecución de `seed.py` | Ejecutar con `PYTHONUTF8=1` (es idempotente). No se cambia código | Workaround |
| H-05 | 2026-10-25 | Bug (original) | Al volver a elegir fecha o servicio se borra la hora pero el resumen sigue visible; al confirmar sale "Elige servicio, día y hora" | Prueba manual con Live Server | `clearTime()` limpia el resumen y vuelve al paso 2 | Resuelto (PR #4) |
| H-06 | 2026-10-25 | Bug (original) | Los errores 422 de FastAPI traen `detail` como lista; el frontend lo trataba como texto | Revisión de código + llamada directa a la API | Se convierte la lista en mensaje legible (público y admin) | Resuelto (PR #4) |
| H-07 | 2026-10-25 | Limitación funcional | Solo se aceptan celulares chilenos (+56); un número de Panamá (+507) es rechazado | Prueba con número real del equipo | Se propone como historia de usuario adicional | Resuelto (US-04, PR #13) |
| H-08 | 2026-10-25 | Código muerto | `e.message === "Error 409"` nunca se cumple porque el backend envía un `detail` propio | Revisión de código | Se eliminó al corregir H-10 (ahora se usa `e.status`) | Resuelto (PR #4) |
| H-09 | 2026-10-25 | Entorno | Live Server recarga la página ante cualquier cambio del workspace (p. ej. `citafacil.db` al reservar) | Análisis preventivo de la IA | Solo se documenta; no se configura nada (la IA lo configuró sin pedirlo y se revirtió, ver Cambios rechazados #2) | Informativo |
| H-10 | 2026-10-25 | Regresión (IA) | El arreglo de H-05 provocó que, ante cualquier error al confirmar (p. ej. teléfono inválido), se recargaran los horarios y se perdiera la hora elegida | Prueba manual de QA (Samuel Saenz) con número +507 | Recargar horarios solo en 409 (horario tomado); en validación se conserva la selección | Resuelto (PR #4) |
| H-11 | 2026-10-25 | Código ajeno | `routers/scores.py` es el ranking del videojuego "ÚLTIMA RONDA 3D" del autor original: no tiene relación con reservas y su POST es público sin autenticación | Análisis de arquitectura | Se eliminó `routers/scores.py`, su registro y la mención en la descripción de la API (`main.py`); la tabla `game_scores` desaparece al recrear la BD local | Resuelto (rama `chore/eliminar-router-juego`) |
| H-12 | 2026-10-25 | Bug (original) | La fecha mínima del frontend usa `toISOString()` (UTC): en Panamá, desde las 19:00 "hoy" pasa a ser mañana y no se puede reservar para el mismo día | Análisis de arquitectura | Endpoint `/api/availability/month` devuelve `today` calculado en la zona del negocio; el frontend ya no usa `toISOString()` | Resuelto (US-02, PR #15) |
| H-13 | 2026-10-25 | Configuración | El backend calcula "ahora" con la zona `America/Santiago` (UTC-3), 2 h adelante de Panamá: oculta horarios aún válidos | Análisis de arquitectura | `America/Panama` en US-04 | Resuelto (US-04, PR #13) |
| H-14 | 2026-10-25 | Arquitectura | No hay migraciones: `create_all()` crea tablas nuevas pero no agrega columnas a las existentes | Análisis de arquitectura | Al cambiar el modelo, borrar `backend/citafacil.db` y volver a ejecutar `seed.py` (sin Alembic) | Aceptado |
| H-15 | 2026-10-25 | Diseño de datos | La cita no guarda el precio cobrado: si cambia el precio del servicio, cambia el histórico de ingresos | Análisis de arquitectura | Guardar `price_paid` en la cita (US-01) para usarlo en US-03 | Pendiente |
| H-16 | 2026-10-25 | Código muerto | `format_cl_phone` no se usaba en ningún lugar del proyecto | Plan de US-04 | Eliminada junto con la validación chilena | Resuelto (US-04, PR #13) |
| H-17 | 2026-10-25 | Configuración | El `backend/.env` local (no versionado) tenía `America/Santiago` y `CLP` y tiene prioridad sobre el código: la app seguía como Chile | Plan de US-04; confirmado por el test `test_config_panama`, que falló | Se actualizó el `.env` local; cada integrante debe actualizar el suyo (ver ARQUITECTURA.md §5) | Resuelto (local) |
| H-18 | 2026-10-25 | Testing | Los tests leen el `.env` del desarrollador: el resultado de `test_config_panama` depende de la configuración local de cada integrante | Fallo de `test_config_panama` | Opción B: los tests fijan zona horaria, moneda, horario y días cerrados con variables de entorno | Resuelto (rama `test/aislar-config`) |
| H-19 | 2026-10-26 | Testing (riesgo) | La configuración de prueba (BD temporal) estaba dentro de `test_booking.py`. Un segundo archivo de tests que importara la app antes habría usado la BD real del `.env`, y el fixture `drop_all` la habría borrado | Al planificar `test_accounts.py` | Se movió la configuración y el fixture a `tests/conftest.py`, que pytest carga antes que cualquier test | Resuelto (US-01 A) |
| H-20 | 2026-10-26 | Limitación conocida | No se verifica que el correo pertenezca al cliente: la app no envía correos | Decisión de diseño de US-01 | Documentado; fuera del alcance de esta versión | Aceptado |
| H-21 | 2026-10-26 | Deuda técnica (original) | `Appointment.created_at` usa `datetime.utcnow`, obsoleto en Python 3.12 (genera advertencias en los tests) | Advertencias de pytest | Las tablas nuevas usan `utc_now()`; la del código original se deja igual por ahora | Pendiente (menor) |

---

## 3. Respuestas incorrectas de la IA

| # | Fecha | Qué dijo / hizo la IA | Por qué era incorrecto | Cómo se corrigió |
|---|---|---|---|---|
| 1 | 2026-10-25 | Intentó `git push` asumiendo que había credenciales disponibles | El agente no tenía sesión de GitHub; el push falló | Push manual por el usuario (H-00) |
| 2 | 2026-10-25 | Intentó instalar dependencias en Python 3.13 sin verificar compatibilidad con las versiones fijadas | El proyecto fija Python 3.12 (`render.yaml`); dos paquetes no tienen binarios para 3.13 | Se instaló Python 3.12 (H-01) |
| 3 | 2026-10-25 | Corrigió H-05 haciendo que `loadSlots()` borrara la hora, sin revisar que el `catch` del botón Confirmar también llamaba a `loadSlots()` | Efecto secundario: tras un error de validación se perdía la hora elegida. La IA solo validó sintaxis, no el flujo en el navegador | Detectado por QA manual; corregido en H-10 |
| 4 | 2026-10-25 | Encadenó en un solo comando la edición de la bitácora (script) con el commit y el push; el script falló y el commit `570ba14` se subió diciendo que incluía la bitácora sin incluirla | El commit no se condicionó al éxito del script y el mensaje describía un cambio inexistente | Detectado por la IA al revisar la salida; corregido con el commit `2dd437f` |

---

## 4. Cambios de la IA rechazados o modificados

| # | Fecha | Propuesta de la IA | Decisión | Motivo |
|---|---|---|---|---|
| 1 | 2026-10-25 | Opción B: actualizar dependencias para Python 3.13 | Rechazada | Riesgo de cambios de comportamiento antes de empezar las historias; se prefiere la línea base original |
| 2 | 2026-10-25 | La IA configuró Live Server (`.vscode/settings.json`) sin que se lo pidieran; el usuario solo había preguntado si funcionaba | Rechazada y eliminada | Cambio no solicitado: la consulta era informativa |
| 3 | 2026-10-25 | Usar Alembic para migraciones (1 dependencia nueva, ~30–45 min) | Rechazada | No aumentar la complejidad; la BD local es desechable y se recrea con `seed.py` |
| 4 | 2026-10-25 | US-04: selector de país con buscador propio y ~22 países validados en backend | Modificada | Alcance reducido: solo Panamá (+507), igual que el original con Chile |
| 5 | 2026-10-25 | US-01: login con teléfono + PIN de 6 dígitos y bloqueo tras 5 intentos | Modificada | Se prefiere correo + contraseña (más seguro que un PIN; sin librerías nuevas). Se mantiene el bloqueo por intentos |

---

## 5. Decisiones tomadas por humanos

| # | Fecha | Decisión | Alternativas consideradas | Responsable |
|---|---|---|---|---|
| 1 | 2026-10-25 | Usar CitaFácil (FastAPI) como base | Spring + React, Django, Python + MySQL | Grupo |
| 2 | 2026-10-25 | Repo propio (no fork), con el original como `upstream` | Fork | Samuel Saenz |
| 3 | 2026-10-25 | Python 3.12 y versiones originales de dependencias | Actualizar dependencias | Samuel Saenz |
| 4 | 2026-10-25 | Corregir H-05 y H-06 de inmediato; H-07 como historia de usuario | Corregir todo dentro de la historia del calendario | Samuel Saenz |
| 5 | 2026-10-25 | Registrar todos los hallazgos e incidencias en esta bitácora | — | Samuel Saenz |
| 6 | 2026-10-25 | La IA no hace cambios (código, configuración o archivos) sin confirmación previa | Dejar que la IA actúe por iniciativa propia | Samuel Saenz |
| 7 | 2026-10-25 | Eliminar el router del videojuego (H-11) por no ser relevante al proyecto | Mantenerlo | Samuel Saenz |
| 8 | 2026-10-25 | Sin Alembic: recrear la BD local cuando cambie el modelo | Alembic | Samuel Saenz |
| 9 | 2026-10-25 | US-04 solo para Panamá (+507, `America/Panama`) | Varios países con buscador | Samuel Saenz |
| 10 | 2026-10-25 | US-01 con correo + contraseña usando solo la biblioteca estándar (`hashlib.scrypt`, `secrets`) | Teléfono + PIN; librerías externas de autenticación | Samuel Saenz |
| 11 | 2026-10-25 | Aceptar US-05 "Mis reservas" como segunda historia propia | Otra historia | Samuel Saenz |
| 12 | 2026-10-25 | Precios en USD con centavos (p. ej. 12.50) | Dólares enteros | Samuel Saenz |
| 13 | 2026-10-25 | Guardar precios como enteros en centavos (`price_cents`) en BD y API; el frontend los muestra como `$12.50` | Columna decimal | Samuel Saenz |
| 14 | 2026-10-25 | Los tests fijan su propia configuración del negocio (opción B de H-18) | A: depender del `.env` local; C: que la app ignore el `.env` en modo test | Samuel Saenz |
| 15 | 2026-10-25 | Calendario propio en JavaScript puro | FullCalendar (librería por CDN) | Samuel Saenz |
| 16 | 2026-10-25 | Mostrar en cada día el número de horarios libres y resaltar "pocos cupos" (3 o menos) con color ámbar, sin emojis | No mostrar el número | Samuel Saenz |
| 17 | 2026-10-25 | Reservas hasta 3 meses adelante, validado también en el backend (`BOOKING_HORIZON_MONTHS=3`) | Sin límite | Samuel Saenz |
| 18 | 2026-10-26 | Dividir US-01 en 2 PRs: A (cuentas) y B (pago y tarjeta guardada) | Un solo PR | Samuel Saenz |
| 19 | 2026-10-26 | Se puede seguir reservando como invitado, sin cuenta | Exigir registro | Samuel Saenz |
| 20 | 2026-10-26 | Una sola tarjeta guardada por cliente (guardar otra reemplaza la anterior) | Varias tarjetas | Samuel Saenz |
| 21 | 2026-10-26 | Mostrar en el panel admin si la cita está pagada (columna "Pago", PR B) | No mostrarlo | Samuel Saenz |
| 22 | 2026-10-26 | Aceptar como limitación que el correo no se verifica (H-20) | Enviar correo de verificación | Samuel Saenz |

---

## 6. Pruebas automatizadas

| Fecha | Comando | Resultado | Nota |
|---|---|---|---|
| 2026-10-25 | `pytest -v` (antes de PR #1) | 0/6 (6 errores) | H-02 |
| 2026-10-25 | `pytest -v` (después de PR #1) | 6/6 OK | Python 3.12.10 |
| 2026-10-25 | `pytest -q` (main tras PR #3 y #4) | 6/6 OK | Sin regresiones en backend |
| 2026-10-25 | `pytest -q` (rama `chore/eliminar-router-juego`) | 6/6 OK | Rutas verificadas: sin `/api/scores` |
| 2026-10-25 | `pytest -v` (US-04, `.env` con Chile) | 13/14 | Falla `test_config_panama` por H-17 |
| 2026-10-25 | `pytest -v` (US-04, `.env` corregido) | 14/14 OK | 8 tests nuevos de teléfono, configuración y centavos |
| 2026-10-25 | `pytest -q` con config de otro integrante (`CLOSED_WEEKDAYS=5,6`, `OPEN_HOUR=12`, Santiago, CLP) | 11/14 | Reproduce H-18: fallan `test_create_and_conflict`, `test_availability_removes_booked_slot` y `test_config_panama` |
| 2026-10-25 | `pytest -q` misma config, tras aislar los tests | 14/14 OK | H-18 resuelto; también 14/14 con la config normal |
| 2026-10-25 | `pytest -q` (US-02) | 23/23 OK | 9 tests nuevos: estados del mes, día lleno, coherencia con horarios del día, límite de 3 meses, `today` en zona del negocio (H-12), mes inválido y servicio inexistente |
| 2026-10-26 | `pytest -q` (US-01 A) | 40/40 OK | 17 tests nuevos en `test_accounts.py`: hash de contraseña, registro (válido, duplicado, inválidos), login, mismo mensaje para correo inexistente y contraseña incorrecta, bloqueo y desbloqueo, logout, sesión vencida, reserva con sesión, como invitado y con token falso |

## 7. Pruebas manuales (QA)

| # | Fecha | Escenario | Pasos | Resultado esperado | Resultado obtenido | QA | Ref. |
|---|---|---|---|---|---|---|---|
| QA-01 | 2026-10-25 | Línea base: reserva con celular de Panamá | Elegir servicio, fecha y hora; celular `+50763211144`; confirmar | Mensaje de error claro | ❌ "Elige servicio, día y hora." con el resumen aún visible | Samuel Saenz | H-05, H-07 |
| QA-02 | 2026-10-25 | Error de validación tras arreglo inicial de H-05/H-06 | Igual que QA-01 | Mensaje claro y se conserva la hora | ⚠️ Mensaje claro, pero se perdió la hora y el formulario quedó desactivado | Samuel Saenz | H-10 |
| QA-03 | 2026-10-25 | Error de validación tras arreglo de H-10 | Lunes 26-10, 11:30, Corte de pelo; celular `+50763211144`; confirmar | Mensaje claro y se conserva la hora | ✅ "Número de celular chileno inválido…"; resumen y hora conservados | Samuel Saenz | PR #4 |
| QA-04 | 2026-10-25 | Reserva exitosa visible en el panel admin | Reserva con celular `+56 9 1234 5678`; revisar `admin.html` | Reserva creada en estado Pendiente | ✅ Martes 27-10, 15:00, Corte de pelo, Pendiente, teléfono normalizado `+56912345678` | Samuel Saenz | PR #4 |
| QA-05 | 2026-10-25 | US-04: precio con centavos en la página pública | Abrir `index.html` y revisar *Corte + Barba* | Se muestra $12.50 | ✅ $12.50 | Samuel Saenz | PR #13 |
| QA-06 | 2026-10-25 | US-04: reserva con celular de Panamá | Reservar con `+507 6321 1144` | Reserva creada | ✅ Reserva creada | Samuel Saenz | PR #13 |
| QA-07 | 2026-10-25 | US-04: rechazo de celular chileno | Reservar con `+56 9 1234 5678` | Mensaje sobre el formato panameño | ✅ Rechazado con mensaje claro | Samuel Saenz | PR #13 |
| QA-08 | 2026-10-25 | US-04: crear servicio con centavos en el panel admin | Crear servicio de $9.75 | Se guarda y se muestra $9.75 | ✅ Se muestra $9.75 | Samuel Saenz | PR #13 |
| QA-09 | 2026-10-25 | US-02: calendario del mes actual | Elegir *Corte de pelo* | Octubre 2026 con nº de horarios libres, domingo 25 tachado y ‹ desactivada | ✅ Como se esperaba | Samuel Saenz | PR #15 |
| QA-10 | 2026-10-25 | US-02: límite de 3 meses | Avanzar con › | Llega a enero 2027, días tras el 25 atenuados y › desactivada | ✅ Como se esperaba | Samuel Saenz | PR #15 |
| QA-11 | 2026-10-25 | US-02: reservar descuenta horarios | Reservar y recargar | El día muestra un horario menos | ✅ Verificado con las reservas del 27-10 | Samuel Saenz | PR #15 |
| QA-12 | 2026-10-25 | US-02: pocos cupos | Servicio *Jornada* (480 min); reservar *Corte de pelo* 10:00 y 10:30 el 27-10; elegir *Jornada* | El 27 muestra 3 en ámbar | ✅ 3 en ámbar (captura) | Samuel Saenz | PR #15 |
| QA-13 | 2026-10-25 | US-02: día lleno | Con *Jornada*, reservar el 27-10 a las 12:00 | El 27 pasa a "lleno" en rojo | ✅ Confirmado por el QA | Samuel Saenz | PR #15 |

> Nota QA-04: la reserva exitosa se hizo en otro horario (27-10 15:00), no como continuación directa de QA-03; la secuencia "error → corregir teléfono → confirmar mismo horario" no quedó registrada por separado.
