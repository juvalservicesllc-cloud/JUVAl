# ADR-016: FastAPI como framework de backend para la PWA (Fase 4A)

- Estado: Aceptada — aprobada explícitamente por el usuario 2026-08-17
  ("BACKEND: FastAPI"), tras una sesión previa de comparación
  arquitectónica (FastAPI vs. Flask vs. Django, ver
  `docs/PROJECT_STATUS.md`).
- Fecha: 2026-08-17

## Contexto

ADR-014 (`Aceptada`) eligió PWA como interfaz principal de Juval, dejando
explícitamente pendiente el framework de backend concreto (ver ADR-014
§"Límites explícitos de esta decisión"). `interfaces/api/` seguía vacío,
solo `README.md`.

## Problema

Exponer `application.run_pipeline` (y el resto del Core ya implementado
y probado — 188 tests al momento de esta decisión) vía HTTP, sin
duplicar ninguna regla de negocio, sin comprometerse a ninguna base de
datos nueva, y sin introducir infraestructura que el proyecto no
necesita todavía (ADR-001, `CLAUDE.md` §4/§14).

## Opciones consideradas

### FastAPI
- Acepta `dataclasses` nativamente en request/response — el Core ya es
  100% `dataclasses`, sin fricción de traducción hacia un ORM u otro
  framework de modelado.
- Tipado + validación + OpenAPI automático a partir de la misma
  anotación de tipo que el equipo ya usa en todo `domain/`/`processing/`.
- Soporte async nativo (ASGI) que absorbe el I/O de red sin forzar a
  reescribir el Core síncrono — Starlette ejecuta funciones síncronas
  en un threadpool automáticamente.
- Testing sin servidor real (`TestClient`/`httpx`), mismo patrón ya
  usado por `tests/integration/test_cli.py` (invocar directamente).
- No fuerza ningún ORM ni ninguna decisión de persistencia.

### Flask
- Minimalismo comparable, agnóstico de framework de datos.
- Sin tipado/OpenAPI nativo — requeriría una extensión adicional
  (`flask-pydantic`/`marshmallow`) para lograr lo que se pide en
  `docs/architecture/API_CONTRACT.md` (contrato validado, documentado),
  es decir, terminaría reconstruyendo a mano lo que FastAPI da de fábrica
  con el mismo esfuerzo de escritura.
- Sync por defecto (WSGI) — viable para el volumen actual, pero sin la
  ventaja de absorción de I/O async que FastAPI ya ofrece sin coste
  adicional.

### Django
- Trae ORM, sistema de migraciones, admin y auth propios — todo esto
  empuja hacia decisiones de persistencia/autenticación que el proyecto
  marca explícitamente `PENDING` (`CLAUDE.md` §14: "no introducir hasta
  necesidad real"). Adoptar Django significaría, de facto, comprometerse
  a su ORM en vez de reutilizar el puerto `ExecutionRunStore` (ADR-013)
  ya definido, o mantener dos sistemas de acceso a datos en paralelo.
  Descartado por desalineación directa con decisiones ya tomadas, no
  por ser "peor" en abstracto.

## Decisión

Juval usa **FastAPI** para `interfaces/api/`. Implementado en
`src/juval/interfaces/api/{main,models,service}.py` (Fase 4A,
2026-08-17):

- `main.py` — la app FastAPI y los endpoints (`POST /api/v1/runs`,
  `GET /api/v1/runs/{execution_id}/download`). Cliente delgado puro
  sobre `application.run_pipeline` (ADR-001) — no calcula profit, ROI,
  margin, score, decisión, ni severidad.
- `models.py` — modelos Pydantic (`ThresholdsIn`, `FeesIn`,
  `RunResponse`, ...) que validan la *forma* del request y serializan
  la respuesta. **Nunca** se convierten en modelos de dominio — la
  traducción explícita vive en `service.py::thresholds_from_in`/
  `fees_from_in`.
- `service.py` — traducción HTTP↔Core, construcción de
  `Thresholds`/`FeeInputs` (misma regla que el CLI: sin defaults
  comerciales, ADR-007), serialización de `SourcingRecord` a JSON
  preservando `value`+`status` juntos por campo sensible (ADR-003/
  ADR-004 — estructuralmente paralelo a `exporter.py::_row_for_record`,
  no una segunda implementación de ningún cálculo), y gestión de
  archivos temporales.

## Consecuencias

- Positivas: 19 tests de integración nuevos (`tests/integration/test_api.py`),
  todos contra el Core real (fixture real, `run_pipeline()` real, sin
  mocks en el camino principal); contrato autodocumentado (`/docs`,
  OpenAPI); cero cambio en `domain/`, `processing/`, ni
  `application/run_pipeline.py`.
- Negativas: 4 dependencias nuevas (`fastapi`, `uvicorn`,
  `python-multipart`, y `httpx` como dependencia de test) — evaluadas y
  justificadas explícitamente en esta ADR, no agregadas sin análisis.
- Reversibilidad: alta — `interfaces/api/` es una capa de cliente
  delgado; cambiar de framework más adelante no tocaría `domain/`,
  `processing/`, ni `application/` (mismo argumento de ADR-001/ADR-005).

## Alternativas rechazadas

Flask (viable pero reconstruye a mano lo que FastAPI da nativo) y
Django (ORM/auth propios en tensión directa con decisiones `PENDING`
ya documentadas) — ver comparación completa arriba.

## Relación con ADR-001

Aplicación directa: `interfaces/api/` es un cliente delgado del
Application Layer, exactamente como ADR-001 exige para cualquier
interfaz. Ningún endpoint contiene una regla de validación,
enriquecimiento, o clasificación — todas viven en `processing/`/
`domain/`, sin cambios.

## Relación con Fase 4

Cierra la decisión de framework backend que `docs/PROJECT_PLAN.md` §4
listaba como `PENDING` tras ADR-014. Fase 4 (global) **no** se declara
`COMPLETE` por esta ADR — falta framework frontend (aprobado
posteriormente, ver ADR-017 si se crea), deployment, y el resto del
Completion Gate de `docs/PHASE_GATES.md` §Fase 4 (frontend, PWA
instalable, E2E, seguridad, validación completa). Este ADR cubre
únicamente Fase 4A (backend).

## Relacionado

ADR-001, ADR-005, ADR-007, ADR-013, ADR-014,
`docs/architecture/API_CONTRACT.md`, `docs/PROJECT_PLAN.md` §Fase 4,
`src/juval/interfaces/cli/main.py` (mismo patrón de cliente delgado ya
validado, referencia arquitectónica reutilizada para esta
implementación).
