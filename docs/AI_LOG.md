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
| 14 | 2026-10-26 | Código / Testing | Claude Code | Implementar US-01 parte A (#10): cuentas de cliente con correo y contraseña, solo biblioteca estándar | Registro, login con bloqueo tras 5 intentos, logout, `/api/me`, reservas asociadas al cliente y frontend con ventana de acceso; 17 tests nuevos (40/40). Detectó el riesgo H-19 al separar los tests y lo resolvió con `conftest.py`. Evitó insertar el nombre del cliente como HTML | Aceptado; QA aprobado (QA-14 a QA-20), PR #16 | H-19, H-20, H-21 |
| 15 | 2026-10-26 | Código / Testing | Claude Code | Implementar US-01 parte B (#10): pago simulado obligatorio, tarjeta guardada (una por cliente), tarjeta de prueba rechazada y columna Pago en admin | Validación de tarjeta (Luhn, marca, vencimiento, CVV), cobro antes de crear la cita, endpoints `/api/me/card`; 19 tests nuevos y 7 existentes adaptados al pago obligatorio (59/59). En su autorrevisión corrigió una aserción vacía en un test y un caso en que la tarjeta guardada no se cargaba al recargar la página | Aceptado; QA aprobado (QA-21 a QA-27), PR #17 | H-15, H-22, H-23 |
| 16 | 2026-10-26 | Seguridad | Claude Code | Corregir H-23 y agregar política de contraseña (rama `fix/seguridad`) | Escape de nombre, teléfono, servicio y tarjeta en la tabla del admin; contraseña con mayúscula, minúscula y número validada en backend, con guía visual en el registro; 7 tests nuevos (66/66). Se comprobó que el test de H-23 falla con la versión sin arreglo | Aceptado; QA aprobado (QA-28 a QA-32), PR #18 | H-23 |
| 17 | 2026-10-26 | Código / Testing | Claude Code | Implementar US-03 (#12): histórico de ejemplo, previsión de demanda con sugerencias y vista "Ver Estadísticas" con Chart.js | `seed_history.py` (~6 meses, reproducible, sin solapes), endpoint `/api/admin/forecast` (promedio de 8 semanas + tendencia lineal, horizonte 1–3 meses), pestañas Reservas / Ver Estadísticas, 4 gráficos, KPIs y sugerencias; 12 tests nuevos (78/78). La IA corrigió dos fallos de su propio diseño antes del commit (ver respuestas incorrectas #6 y #7) | Aceptado; QA aprobado (QA-33 a QA-39) con observaciones de revisión → Issue #20; PR #19 | — |
| 18 | 2026-10-26 | Revisión / Código | Claude Code | Iteración #20 (sub-issue de #12) a partir de la revisión funcional: tabla con desplazamiento, histórico liviano, rango de fechas, filtro cruzado por servicio y KPIs nuevos | Endpoint con `start`, `end` y `service_id`; días pasados = datos reales, desde hoy = previsión; servicios arriba y clicables; ticket promedio y tasa de cancelación; histórico de 299 citas en 3 meses; 21 tests de previsión (86/86). Con los datos livianos se vio que las sugerencias con umbral absoluto no servían y se pasó a una clasificación relativa (respuesta incorrecta #8) | Aceptado; QA aprobado (QA-40 a QA-45), PR #21 | H-24, H-25, H-26 |
| 19 | 2026-10-26 | Debug / Código | Claude Code | Explicar por qué el KPI "Citas" (20) no coincidía con el gráfico de servicios (21) con el filtro Corte niño, y ajustar la vista según el revisor | Consultó la BD: el gráfico contaba reales + reservadas (20 + 1) y el KPI reales + previstas, con la previsión en 0 porque la tendencia (−30 %/semana) se proyectaba a cero. Corrigió el modelo (tendencia amortiguada, previsión ≥ reservado), separó citas e ingresos por servicio, movió las sugerencias al final con un botón que desplaza hasta ellas; 2 tests nuevos (88/88) | Aceptado; QA aprobado (QA-46 a QA-50), PR #22 | H-27 |
| 20 | 2026-10-26 | Validación / Código | Claude Code | Validar uno por uno los datos de "Ver Estadísticas" contra la BD y la pestaña Reservas; luego separar datos reales y previsión con un interruptor | 14 cruces con la BD: sin conteos dobles; el desajuste (471 vs 301) venía de mezclar estimaciones con datos reales y de categorías solapadas ("previstas" incluía "reservadas"). Respuesta reestructurada en `real` y `forecast`; interruptor "Mostrar previsión" apagado por defecto; test de conciliación con Reservas (90/90) | Aceptado; QA aprobado (QA-46 a QA-50), PR #22 | H-28 |
| 21 | 2026-10-26 | Análisis / Código / Testing | Claude Code | Validar e implementar US-05 (#11): ver, cancelar y reprogramar las reservas propias | Al validar reprogramar detectó que la disponibilidad contaba la propia cita como ocupada (H-29). Endpoints `/api/me/appointments`, `/cancel` (reembolso simulado) y `/reschedule`; `exclude_id` solo válido para el dueño; pestañas Reservar / Mis reservas con contadores, filtro y lista con desplazamiento; modo reprogramar sobre el calendario del paso 2; 10 tests nuevos (100/100). Un error propio rompió la sintaxis de `notifications.py` y lo detectaron los tests (respuesta incorrecta #11) | Aceptado; pendiente QA manual | H-29 |

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
| H-15 | 2026-10-25 | Diseño de datos | La cita no guarda el precio cobrado: si cambia el precio del servicio, cambia el histórico de ingresos | Análisis de arquitectura | La cita guarda `price_paid_cents` al momento del pago (test `test_price_paid_kept_when_service_price_changes`) | Resuelto (US-01 B, PR #17) |
| H-16 | 2026-10-25 | Código muerto | `format_cl_phone` no se usaba en ningún lugar del proyecto | Plan de US-04 | Eliminada junto con la validación chilena | Resuelto (US-04, PR #13) |
| H-17 | 2026-10-25 | Configuración | El `backend/.env` local (no versionado) tenía `America/Santiago` y `CLP` y tiene prioridad sobre el código: la app seguía como Chile | Plan de US-04; confirmado por el test `test_config_panama`, que falló | Se actualizó el `.env` local; cada integrante debe actualizar el suyo (ver ARQUITECTURA.md §5) | Resuelto (local) |
| H-18 | 2026-10-25 | Testing | Los tests leen el `.env` del desarrollador: el resultado de `test_config_panama` depende de la configuración local de cada integrante | Fallo de `test_config_panama` | Opción B: los tests fijan zona horaria, moneda, horario y días cerrados con variables de entorno | Resuelto (rama `test/aislar-config`) |
| H-19 | 2026-10-26 | Testing (riesgo) | La configuración de prueba (BD temporal) estaba dentro de `test_booking.py`. Un segundo archivo de tests que importara la app antes habría usado la BD real del `.env`, y el fixture `drop_all` la habría borrado | Al planificar `test_accounts.py` | Se movió la configuración y el fixture a `tests/conftest.py`, que pytest carga antes que cualquier test | Resuelto (US-01 A, PR #16) |
| H-20 | 2026-10-26 | Limitación conocida | No se verifica que el correo pertenezca al cliente: la app no envía correos | Decisión de diseño de US-01 | Documentado; fuera del alcance de esta versión | Aceptado |
| H-21 | 2026-10-26 | Deuda técnica (original) | `Appointment.created_at` usa `datetime.utcnow`, obsoleto en Python 3.12 (genera advertencias en los tests) | Advertencias de pytest | Las tablas nuevas usan `utc_now()`; la del código original se deja igual por ahora | Pendiente (menor) |
| H-22 | 2026-10-26 | Seguridad (original) | El mensaje final de la reserva insertaba el celular escrito por el usuario como HTML | Revisión al modificar ese mensaje en US-01 B | Se escapa el texto (`esc()`) en ese mensaje | Resuelto (US-01 B, PR #17) |
| H-23 | 2026-10-26 | Seguridad (original) | El panel admin inserta como HTML el nombre del cliente (`innerHTML`). Cualquier visitante puede reservar con un nombre que contenga código, y ese código se ejecutaría en el navegador del administrador (XSS almacenado) | Revisión del panel admin al agregar la columna Pago | Escape (`esc()`) al mostrar nombre, teléfono, servicio y tarjeta en la tabla del admin. Test `test_frontend_security.py` (estático + ejecución real con Node.js) | Resuelto (PR #18) |
| H-24 | 2026-10-26 | Usabilidad | La tabla de reservas del admin no tenía límite de alto: con el histórico se volvía interminable y ocultaba la sección de servicios | Revisión funcional (Samuel Saenz) | Caja con desplazamiento interno y encabezados fijos | Resuelto (#20, PR #21) |
| H-25 | 2026-10-26 | Inconsistencia (IA) | El filtro de "Ver Estadísticas" solo afectaba a la previsión: el gráfico semanal mostraba siempre 6 meses y el de ingresos otro periodo | Revisión funcional (Samuel Saenz) | Un único rango de fechas (desde/hasta) filtra todos los gráficos y KPIs | Resuelto (#20, PR #21) |
| H-26 | 2026-10-26 | Datos de demo | El histórico de ejemplo (~1.500 citas en 6 meses) era excesivo para una demo | Revisión funcional (Samuel Saenz) | `seed_history.py`: ~300 citas en 3 meses, con variación diaria (días flojos y buenos) | Resuelto (#20, PR #21) |
| H-27 | 2026-10-26 | Error de cálculo (IA) | Con el filtro Corte niño el KPI "Citas" daba 20 y el gráfico 21: la previsión era 0 (tendencia de −30 %/semana extrapolada sin límite) e ignoraba una cita ya reservada | QA del revisor (Samuel Saenz) con rango junio–enero | Tendencia amortiguada (±10 %/semana, piso del 50 % del promedio) y previsión diaria nunca menor que lo reservado; etiquetas "reales + reservadas" / "reales + previstas" | Resuelto (PR #22) |
| H-28 | 2026-10-26 | Presentación (IA) | "Ver Estadísticas" mostraba 471 citas y la pestaña Reservas 301: los KPIs sumaban citas reales con estimaciones y "previstas" ya incluía las "reservadas" sin decirlo | Revisión del QA (Samuel Saenz) comparando ambas pestañas | Datos reales por defecto (total 301 = 282 registradas + 19 canceladas, igual que Reservas); la previsión solo con el interruptor, en una fila de KPIs aparte y con estilo punteado "(estimado)"; test `test_real_counts_reconcile_with_reservations_tab` | Resuelto (PR #22) |
| H-29 | 2026-10-26 | Diseño (detectado por la IA) | Al reprogramar, la verificación de horarios libres contaba la propia cita como ocupada: no se podía mover una cita a un horario que se solapara con su horario actual (p. ej. 10:00 → 10:30 en un servicio de 60 min) | Validación previa de US-05 | `exclude_id` en la disponibilidad; en los endpoints públicos solo se respeta si la cita es del cliente con sesión (tests `test_reschedule_can_overlap_its_own_current_slot` y `test_exclude_is_ignored_for_other_customers`) | Resuelto (rama `feature/US-05-mis-reservas`) |

---

## 3. Respuestas incorrectas de la IA

| # | Fecha | Qué dijo / hizo la IA | Por qué era incorrecto | Cómo se corrigió |
|---|---|---|---|---|
| 1 | 2026-10-25 | Intentó `git push` asumiendo que había credenciales disponibles | El agente no tenía sesión de GitHub; el push falló | Push manual por el usuario (H-00) |
| 2 | 2026-10-25 | Intentó instalar dependencias en Python 3.13 sin verificar compatibilidad con las versiones fijadas | El proyecto fija Python 3.12 (`render.yaml`); dos paquetes no tienen binarios para 3.13 | Se instaló Python 3.12 (H-01) |
| 3 | 2026-10-25 | Corrigió H-05 haciendo que `loadSlots()` borrara la hora, sin revisar que el `catch` del botón Confirmar también llamaba a `loadSlots()` | Efecto secundario: tras un error de validación se perdía la hora elegida. La IA solo validó sintaxis, no el flujo en el navegador | Detectado por QA manual; corregido en H-10 |
| 4 | 2026-10-25 | Encadenó en un solo comando la edición de la bitácora (script) con el commit y el push; el script falló y el commit `570ba14` se subió diciendo que incluía la bitácora sin incluirla | El commit no se condicionó al éxito del script y el mensaje describía un cambio inexistente | Detectado por la IA al revisar la salida; corregido con el commit `2dd437f` |
| 5 | 2026-10-26 | Escribió en un test la aserción `"123" not in appt.payment_last4`, que se cumple siempre y no prueba nada sobre el CVV | Aserción vacía: daba falsa seguridad | Detectado por la IA al revisar sus tests antes del commit; reemplazada por una verificación de que no existe columna para el CVV ni el número |
| 6 | 2026-10-26 | Midió la ocupación en minutos de servicio en vez de turnos bloqueados | En una agenda por turnos de 30 min, un servicio de 20 min bloquea el turno entero: la ocupación quedaba subestimada (tope real ≈ 80 % aun con el día lleno) y nunca aparecía la sugerencia de alta demanda | Detectado por la IA al revisar los resultados del histórico de ejemplo; se mide en turnos bloqueados (test `test_occupancy_counts_blocked_slots`) |
| 7 | 2026-10-26 | La previsión semanal sumaba solo los días desde hoy | La semana actual aparecía con una caída falsa en el gráfico | Detectado por la IA al diseñar el gráfico; se usa el total del modelo para la semana completa (verificado en `test_constant_demand_split_by_weekday`) |
| 8 | 2026-10-26 | Clasificó la demanda con umbrales absolutos (< 40 % = baja) | Con un negocio de ocupación moderada todos los días y casi todas las horas eran "baja demanda": la sugerencia no ayudaba a decidir | Detectado por la IA al probar con el histórico liviano; días y horas se comparan contra el promedio del negocio (≥ 125 % mayor, ≤ 75 % menor) y el 85 % absoluto queda solo para "casi lleno" (test `test_days_classified_against_business_average`) |
| 9 | 2026-10-26 | Proyectó la tendencia lineal sin límite y permitió prever menos citas que las ya reservadas | Con pocos datos, un mes flojo llevaba la previsión de un servicio a 0 ("nadie volverá a pedirlo") y el KPI ignoraba reservas reales | Detectado por el revisor (H-27); corregido con tendencia amortiguada y piso (tests `test_declining_trend_is_damped_and_floored` y `test_forecast_never_below_booked`) |
| 10 | 2026-10-26 | Mezcló en los mismos KPIs citas reales y estimadas, con categorías que se solapaban | Era imposible cuadrar "Ver Estadísticas" con la pestaña Reservas y el revisor pensó que había conteos dobles | Detectado por el revisor (H-28); se separaron por completo las secciones real y previsión |
| 11 | 2026-10-26 | Al agregar los mensajes de WhatsApp de cancelación y cambio, escapó mal los saltos de línea en el script de edición y dejó cadenas partidas en `notifications.py` | Error de sintaxis: la app no arrancaba | Detectado al correr los tests antes del commit; corregido con la herramienta de edición |

---

## 4. Cambios de la IA rechazados o modificados

| # | Fecha | Propuesta de la IA | Decisión | Motivo |
|---|---|---|---|---|
| 1 | 2026-10-25 | Opción B: actualizar dependencias para Python 3.13 | Rechazada | Riesgo de cambios de comportamiento antes de empezar las historias; se prefiere la línea base original |
| 2 | 2026-10-25 | La IA configuró Live Server (`.vscode/settings.json`) sin que se lo pidieran; el usuario solo había preguntado si funcionaba | Rechazada y eliminada | Cambio no solicitado: la consulta era informativa |
| 3 | 2026-10-25 | Usar Alembic para migraciones (1 dependencia nueva, ~30–45 min) | Rechazada | No aumentar la complejidad; la BD local es desechable y se recrea con `seed.py` |
| 4 | 2026-10-25 | US-04: selector de país con buscador propio y ~22 países validados en backend | Modificada | Alcance reducido: solo Panamá (+507), igual que el original con Chile |
| 5 | 2026-10-25 | US-01: login con teléfono + PIN de 6 dígitos y bloqueo tras 5 intentos | Modificada | Se prefiere correo + contraseña (más seguro que un PIN; sin librerías nuevas). Se mantiene el bloqueo por intentos |
| 6 | 2026-10-26 | Además de escapar, validar el nombre en el backend con una lista de caracteres permitidos (defensa en profundidad) | Rechazada | El equipo prefirió el plan original: solo escapar al mostrar en el admin |
| 7 | 2026-10-26 | Horizonte de previsión seleccionable en meses (1, 2 o 3) | Modificada | El revisor propuso un rango desde/hasta que filtre todos los gráficos |
| 8 | 2026-10-26 | Mantener un histórico grande para que aparezca "alta demanda" en la demo | Rechazada | Se prefirió un histórico liviano y realista, con días de poca demanda |
| 9 | 2026-10-26 | Mostrar "Citas registradas / Previsión adicional / Total esperado" como KPIs juntos | Rechazada | El revisor prefirió datos reales por defecto y la previsión aparte |
| 10 | 2026-10-26 | Sub-pestañas "Datos reales" y "Previsión" dentro de Ver Estadísticas | Modificada | El revisor eligió un interruptor "Mostrar previsión" sobre los mismos gráficos |
| 11 | 2026-10-26 | "Mis reservas" en una ventana emergente y sin reprogramar | Modificada | El revisor pidió una vista con contadores que escale con muchas citas y validar reprogramar; se implementaron ambas |

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
| 23 | 2026-10-26 | El pago (simulado) es obligatorio para toda reserva nueva | Pago opcional | Samuel Saenz |
| 24 | 2026-10-26 | Incluir la tarjeta de prueba rechazada `4000 0000 0000 0002` para validar el caso de pago fallido | Solo tarjetas aprobadas | Samuel Saenz |
| 25 | 2026-10-26 | Corregir H-23 escapando los datos del cliente al mostrarlos en el admin | Además, validar el nombre al recibirlo | Samuel Saenz |
| 26 | 2026-10-26 | Política de contraseña: 8 caracteres o más, con al menos una mayúscula, una minúscula y un número (solo al crear cuenta) | Solo longitud mínima | Samuel Saenz |
| 27 | 2026-10-26 | Gráficos con Chart.js (CDN, como Font Awesome y las fuentes) | Gráficos hechos a mano en SVG | Samuel Saenz |
| 28 | 2026-10-26 | Incluir sugerencias automáticas de precio e inventario | Solo gráficos | Samuel Saenz |
| 29 | 2026-10-26 | Horizonte de previsión dinámico: 1 mes por defecto, seleccionable hasta 3 meses | Horizonte fijo en semanas | Samuel Saenz |
| 30 | 2026-10-26 | Panel admin con dos pestañas: "Reservas" (por defecto) y "Ver Estadísticas" | Gráficos debajo de las reservas; botón que alterna | Samuel Saenz |
| 31 | 2026-10-26 | Tabla de reservas en una caja con desplazamiento interno | Paginación | Samuel Saenz |
| 32 | 2026-10-26 | Histórico de demo: ~300 citas en 3 meses, sin días llenos | 40 citas; ~1.500 en 6 meses | Samuel Saenz |
| 33 | 2026-10-26 | Rango de fechas desde/hasta, por defecto últimas 4 semanas + próximo mes, que filtra todos los gráficos | Horizonte en meses | Samuel Saenz |
| 34 | 2026-10-26 | Filtro cruzado solo por servicio, con el gráfico de servicios arriba y botón "Limpiar filtros" | Filtrar también por día u hora | Samuel Saenz |
| 35 | 2026-10-26 | KPIs nuevos: ticket promedio y tasa de cancelación | Mantener los KPIs anteriores | Samuel Saenz |
| 36 | 2026-10-26 | Registrar la iteración como sub-issue (#20) de US-03 en lugar de reabrir #12 | Reabrir #12 | Samuel Saenz |
| 37 | 2026-10-26 | Amortiguar la tendencia (±10 %/semana, piso del 50 %) y no prever menos que lo reservado | Recta sin límite | Samuel Saenz |
| 38 | 2026-10-26 | Sugerencias al final de la vista, con un botón destacado arriba que muestra cuántas hay y desplaza hasta ellas | Sugerencias arriba | Samuel Saenz |
| 39 | 2026-10-26 | Separar "Citas por servicio" e "Ingresos por servicio" en dos gráficos, ambos clicables para filtrar | Un solo gráfico con ingresos y citas en el detalle | Samuel Saenz |
| 40 | 2026-10-26 | Datos reales por defecto; previsión solo con el interruptor "Mostrar previsión", sobre los mismos gráficos pero claramente diferenciada (US-03 se cumple al activarlo) | Quitar la previsión; sub-pestañas | Samuel Saenz |
| 41 | 2026-10-26 | En datos reales mostrar primero el total de reservas y luego las citas registradas | Solo registradas | Samuel Saenz |
| 42 | 2026-10-26 | Tasa de cancelación sobre el total del rango (canceladas / total) | Solo sobre días pasados | Samuel Saenz |
| 43 | 2026-10-26 | "Ingresos cobrados" incluye las reservas futuras (se pagan por adelantado) | Solo citas realizadas | Samuel Saenz |
| 44 | 2026-10-26 | Cancelar y reprogramar hasta 24 h antes de la cita (`CANCEL_MIN_HOURS`) | Sin plazo; otro plazo | Samuel Saenz |
| 45 | 2026-10-26 | Al cancelar, reembolso completo (simulado), visible como "Reembolsado" en el admin | Sin reembolso | Samuel Saenz |
| 46 | 2026-10-26 | "Mis reservas" como pestaña de la página (con contadores total/programadas/completadas/canceladas, filtro y lista con desplazamiento) | Ventana emergente | Samuel Saenz |
| 47 | 2026-10-26 | Incluir reprogramar: solo fecha y hora (mismo servicio y pago), sin límite de veces | No reprogramar; permitir cambiar de servicio | Samuel Saenz |

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
| 2026-10-26 | `pytest -q` (US-01 B) | 59/59 OK | 19 tests nuevos en `test_payments.py` (Luhn, marcas, errores de tarjeta, pago obligatorio, tarjeta rechazada sin cita, precio pagado fijo, tarjeta guardada, una por cliente, sesión requerida); 7 tests existentes adaptados al pago obligatorio |
| 2026-10-26 | `pytest -q` (fix/seguridad) | 66/66 OK | 7 tests nuevos: 4 casos de política de contraseña, login sin validar reglas, escape en el admin (estático) y `esc()` ejecutado con Node.js (se omite si no hay Node). El test de H-23 falla con la versión de `main` sin arreglo |
| 2026-10-26 | `pytest -q` (US-03) | 78/78 OK | 12 tests nuevos en `test_forecast.py`: recta de tendencia, turnos bloqueados, demanda constante repartida por día, tendencia creciente, canceladas excluidas, ingresos con precio pagado, horizonte y días cerrados, reservas ya tomadas, sin histórico, sugerencias, token y rango de meses. `seed_history.py` verificado en BD temporal: 0 solapes, 0 domingos, idempotente |
| 2026-10-26 | `pytest -q` (#20) | 86/86 OK | `test_forecast.py` reescrito (21 tests): rango con datos reales y previsión, valores por defecto, validaciones (hasta < desde, límite de reservas, > 1 año, servicio inexistente), filtro por servicio, base de la ocupación por hora, KPIs de ticket y cancelación, clasificación relativa |
| 2026-10-26 | `pytest -q` (fix/prevision-ajustes) | 88/88 OK | 2 tests nuevos: tendencia decreciente amortiguada con piso y previsión nunca menor que lo reservado; el de tendencia creciente se ajustó a la pendiente amortiguada |
| 2026-10-26 | `pytest -q` (H-28) | 90/90 OK | `test_forecast.py` reescrito para las secciones `real` y `forecast`: conciliación con /api/admin/stats, ingresos cobrados, base de la ocupación, sección real sin estimaciones, KPI filtrado = barra del servicio, previsión no disponible en rango pasado, sugerencias de previsión rotuladas |
| 2026-10-26 | `pytest -q` (US-05) | 100/100 OK | 10 tests nuevos en `test_my_appointments.py`: sesión requerida, contadores y estados, cancelar con reembolso y horario liberado, cita ajena (404), plazo de 24 h, pasada o ya cancelada, reprogramar a otro día (mismo pago, recordatorio reiniciado), solaparse con su propio horario, `exclude_id` ignorado para otros, horario ocupado / igual / fuera de horario / día cerrado |

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
| QA-14 | 2026-10-26 | US-01 A: crear cuenta | Ingresar → Crear cuenta con correo, contraseña ≥ 8 y celular +507 | Aparecen el nombre y "Salir" | ✅ Como se esperaba | Samuel Saenz | PR #16 |
| QA-15 | 2026-10-26 | US-01 A: datos precargados | Reservar con sesión | Nombre, celular y aviso verde en el paso 3 | ✅ Como se esperaba | Samuel Saenz | PR #16 |
| QA-16 | 2026-10-26 | US-01 A: persistencia de sesión | Recargar la página | Sigue la sesión iniciada | ✅ Como se esperaba | Samuel Saenz | PR #16 |
| QA-17 | 2026-10-26 | US-01 A: salir y volver a entrar | Salir; ingresar con el mismo correo y contraseña | Sesión iniciada de nuevo | ✅ Como se esperaba | Samuel Saenz | PR #16 |
| QA-18 | 2026-10-26 | US-01 A: bloqueo por intentos | 5 contraseñas incorrectas; luego la correcta | "Cuenta bloqueada…" | ✅ Indica esperar 15 min | Samuel Saenz | PR #16 |
| QA-19 | 2026-10-26 | US-01 A: reserva como invitado | Reservar sin sesión | Reserva creada como antes | ✅ Como se esperaba | Samuel Saenz | PR #16 |
| QA-20 | 2026-10-26 | Título del calendario | Abrir el calendario | "Octubre de 2026" | ✅ Corregido | Samuel Saenz | PR #16 |
| QA-21 | 2026-10-26 | US-01 B: invitado paga | Sin sesión, pagar con 4242 4242 4242 4242, 12/30, CVV 123 | Confirmada con "Pago aprobado… Visa •••• 4242" | ✅ Como se esperaba | Samuel Saenz | PR #17 |
| QA-22 | 2026-10-26 | US-01 B: tarjeta rechazada | Pagar con 4000 0000 0000 0002 | "Pago rechazado por el banco…" y se conserva la hora | ✅ Como se esperaba | Samuel Saenz | PR #17 |
| QA-23 | 2026-10-26 | US-01 B: tarjeta inválida | Pagar con 4242 4242 4242 4241 | "Número de tarjeta inválido…" | ✅ Como se esperaba | Samuel Saenz | PR #17 |
| QA-24 | 2026-10-26 | US-01 B: guardar tarjeta | Crear cuenta y reservar marcando "Guardar tarjeta" | Reserva creada y tarjeta guardada | ✅ Como se esperaba | Samuel Saenz | PR #17 |
| QA-25 | 2026-10-26 | US-01 B: pagar con un clic | Otra reserva con sesión | "Usar mi tarjeta Visa •••• 4242" marcado, sin pedir datos | ✅ Como se esperaba | Samuel Saenz | PR #17 |
| QA-26 | 2026-10-26 | US-01 B: persistencia de la tarjeta | Recargar la página | La tarjeta guardada sigue apareciendo | ✅ Como se esperaba | Samuel Saenz | PR #17 |
| QA-27 | 2026-10-26 | US-01 B: columna Pago en admin | Revisar el panel admin | Reservas pagadas con monto y tarjeta; "Sin pago" en las de ejemplo | ✅ Como se esperaba | Samuel Saenz | PR #17 |
| QA-28 | 2026-10-26 | H-23: XSS en el panel admin | Reservar con el nombre `<img src=x onerror=alert('XSS')>` y abrir el admin | Sin alerta; el nombre se ve como texto | ✅ Como se esperaba | Samuel Saenz | PR #18 |
| QA-29 | 2026-10-26 | Guía de contraseña | Crear cuenta escribiendo la contraseña | Cada regla se marca en verde al cumplirse | ✅ Como se esperaba | Samuel Saenz | PR #18 |
| QA-30 | 2026-10-26 | Contraseña débil | Registrarse con `clavesegura` | Indica que falta mayúscula y número | ✅ Como se esperaba | Samuel Saenz | PR #18 |
| QA-31 | 2026-10-26 | Contraseña válida | Registrarse con `Clave2026` | Cuenta creada | ✅ Como se esperaba | Samuel Saenz | PR #18 |
| QA-32 | 2026-10-26 | Cuenta anterior a la política | Iniciar sesión con la cuenta previa | Inicia sesión sin aplicar reglas | ✅ Como se esperaba | Samuel Saenz | PR #18 |
| QA-33 | 2026-10-26 | US-03: vista por defecto | Entrar al admin | Se abre la pestaña Reservas | ✅ Como se esperaba | Samuel Saenz | PR #19 |
| QA-34 | 2026-10-26 | US-03: Ver Estadísticas | Abrir la pestaña | KPIs, sugerencias y 4 gráficos con el tema oscuro | ✅ Como se esperaba | Samuel Saenz | PR #19 |
| QA-35 | 2026-10-26 | US-03: detalle de gráficos | Pasar el mouse sobre los gráficos | Aparece el detalle | ✅ Como se esperaba | Samuel Saenz | PR #19 |
| QA-36 | 2026-10-26 | US-03: horizonte | Cambiar de 1 a 3 meses | Se extiende el gráfico y cambian los KPIs | ✅ Funciona; observación: el gráfico semanal mantiene todo el histórico (H-25) | Samuel Saenz | PR #19 |
| QA-37 | 2026-10-26 | US-03: colores por demanda | Revisar el gráfico por día | Viernes/sábados en ámbar, lunes en gris | ✅ Como se esperaba | Samuel Saenz | PR #19 |
| QA-38 | 2026-10-26 | US-03: volver a Reservas | Tocar Reservas | Todo como antes | ✅ Funciona; observación: la tabla no tiene límite de alto (H-24) | Samuel Saenz | PR #19 |
| QA-39 | 2026-10-26 | US-03: reservas futuras del histórico | Revisar el calendario público | Menos horarios libres las próximas semanas | ✅ Funciona; observación: el histórico es excesivo (H-26) | Samuel Saenz | PR #19 |
| QA-40 | 2026-10-26 | #20: tabla con desplazamiento | Abrir Reservas | Barra propia; servicios a la vista | ✅ Como se esperaba | Samuel Saenz | PR #21 |
| QA-41 | 2026-10-26 | #20: vista por defecto | Abrir Ver Estadísticas | Rango por defecto y servicios arriba | ✅ Como se esperaba | Samuel Saenz | PR #21 |
| QA-42 | 2026-10-26 | #20: atajos y fechas | Probar atajos y fechas a mano | Todo se filtra; no se puede pasar de enero 2027 | ✅ Como se esperaba | Samuel Saenz | PR #21 |
| QA-43 | 2026-10-26 | #20: filtro cruzado | Clic en un servicio y de nuevo en el mismo | Todo se filtra; segundo clic lo quita | ✅ Funciona; observación: con Corte niño y rango junio–enero el KPI (20) no coincidía con el gráfico (21) → H-27 | Samuel Saenz | PR #21 |
| QA-44 | 2026-10-26 | #20: limpiar filtros | Pulsar Limpiar filtros | Vuelve al estado inicial | ✅ Como se esperaba | Samuel Saenz | PR #21 |
| QA-45 | 2026-10-26 | #20: rango solo pasado | Atajo Último mes | Solo datos reales | ✅ Como se esperaba | Samuel Saenz | PR #21 |
| QA-46 | 2026-10-26 | H-28: datos reales cuadran con Reservas | Rango 28/06–22/01 en Ver Estadísticas | 301 / 282 / 19, sin datos estimados | ✅ Como se esperaba | Samuel Saenz | PR #22 |
| QA-47 | 2026-10-26 | H-27/H-28: filtro Corte niño | Filtrar Corte niño | KPI de registradas = barra = 21 | ✅ Como se esperaba | Samuel Saenz | PR #22 |
| QA-48 | 2026-10-26 | Interruptor "Mostrar previsión" | Activarlo | Etiqueta, fila de KPIs y barras punteadas; KPIs reales sin cambios | ✅ Como se esperaba | Samuel Saenz | PR #22 |
| QA-49 | 2026-10-26 | Previsión con rango pasado | Último mes + interruptor | Indica que no hay días que prever | ✅ Como se esperaba | Samuel Saenz | PR #22 |
| QA-50 | 2026-10-26 | Apagar la previsión | Desactivar el interruptor | Vuelve a solo datos reales | ✅ Como se esperaba | Samuel Saenz | PR #22 |

> Nota QA-04: la reserva exitosa se hizo en otro horario (27-10 15:00), no como continuación directa de QA-03; la secuencia "error → corregir teléfono → confirmar mismo horario" no quedó registrada por separado.
