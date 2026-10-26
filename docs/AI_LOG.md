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

---

## 2. Incidencias y hallazgos

| ID | Fecha | Tipo | Descripción | Cómo se detectó | Resolución | Estado |
|---|---|---|---|---|---|---|
| H-00 | 2026-10-25 | Entorno | El agente IA no puede autenticarse en GitHub de forma interactiva | Primer `git push` desde la IA | Login con Git Credential Manager desde la terminal; luego la IA puede hacer push | Resuelto |
| H-01 | 2026-10-25 | Entorno | `psycopg2-binary==2.9.9` y `pydantic==2.7.4` (→ `pydantic-core==2.18.4`) no tienen binarios para Python 3.13 | `pip install` fallido | Instalar Python 3.12 (coincide con `render.yaml`) | Resuelto |
| H-02 | 2026-10-25 | Bug (original) | Los tests usan `sqlite:////tmp/...`; en Windows `C:\tmp` no existe → 6 tests en error | `pytest` línea base | `tempfile.gettempdir()` en `backend/tests/test_booking.py` | Resuelto (PR #1) |
| H-03 | 2026-10-25 | Configuración | El frontend apuntaba siempre a la API de producción en Render | Revisión de código | Usa `http://localhost:8000` si se abre en local | Resuelto (PR #2) |
| H-04 | 2026-10-25 | Bug (original) | `seed.py` falla en consolas Windows (cp1252) al imprimir "✔"; solo se guardan los servicios | Ejecución de `seed.py` | Ejecutar con `PYTHONUTF8=1` (es idempotente). No se cambia código | Workaround |
| H-05 | 2026-10-25 | Bug (original) | Al volver a elegir fecha o servicio se borra la hora pero el resumen sigue visible; al confirmar sale "Elige servicio, día y hora" | Prueba manual con Live Server | `clearTime()` limpia el resumen y vuelve al paso 2 | Resuelto (PR `fix/formulario-reserva`) |
| H-06 | 2026-10-25 | Bug (original) | Los errores 422 de FastAPI traen `detail` como lista; el frontend lo trataba como texto | Revisión de código + llamada directa a la API | Se convierte la lista en mensaje legible (público y admin) | Resuelto (PR `fix/formulario-reserva`) |
| H-07 | 2026-10-25 | Limitación funcional | Solo se aceptan celulares chilenos (+56); un número de Panamá (+507) es rechazado | Prueba con número real del equipo | Se propone como historia de usuario adicional | Pendiente |
| H-08 | 2026-10-25 | Código muerto | `e.message === "Error 409"` nunca se cumple porque el backend envía un `detail` propio | Revisión de código | Sin cambio: el mensaje del backend ya es correcto | Aceptado |
| H-09 | 2026-10-25 | Entorno | Live Server recarga la página ante cualquier cambio del workspace (p. ej. `citafacil.db` al reservar) | Análisis preventivo de la IA | Solo se documenta; no se configura nada (la IA lo configuró sin pedirlo y se revirtió, ver Cambios rechazados #2) | Informativo |

---

## 3. Respuestas incorrectas de la IA

| # | Fecha | Qué dijo / hizo la IA | Por qué era incorrecto | Cómo se corrigió |
|---|---|---|---|---|
| 1 | 2026-10-25 | Intentó `git push` asumiendo que había credenciales disponibles | El agente no tenía sesión de GitHub; el push falló | Push manual por el usuario (H-00) |
| 2 | 2026-10-25 | Intentó instalar dependencias en Python 3.13 sin verificar compatibilidad con las versiones fijadas | El proyecto fija Python 3.12 (`render.yaml`); dos paquetes no tienen binarios para 3.13 | Se instaló Python 3.12 (H-01) |

---

## 4. Cambios de la IA rechazados o modificados

| # | Fecha | Propuesta de la IA | Decisión | Motivo |
|---|---|---|---|---|
| 1 | 2026-10-25 | Opción B: actualizar dependencias para Python 3.13 | Rechazada | Riesgo de cambios de comportamiento antes de empezar las historias; se prefiere la línea base original |
| 2 | 2026-10-25 | La IA configuró Live Server (`.vscode/settings.json`) sin que se lo pidieran; el usuario solo había preguntado si funcionaba | Rechazada y eliminada | Cambio no solicitado: la consulta era informativa |

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

---

## 6. Pruebas automatizadas

| Fecha | Comando | Resultado | Nota |
|---|---|---|---|
| 2026-10-25 | `pytest -v` (antes de PR #1) | 0/6 (6 errores) | H-02 |
| 2026-10-25 | `pytest -v` (después de PR #1) | 6/6 OK | Python 3.12.10 |
