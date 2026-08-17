# Juval — Technology Decisions

Matriz de estado por tecnología. Estados usados, con el mismo
significado que en el resto de `docs/`:

- **APPROVED** — en uso real hoy, respaldado por código y/o un ADR
  aceptado.
- **PROPOSED** — mencionada como opción candidata en `docs/`, sin ADR
  que la apruebe; su mención no constituye aprobación.
- **PENDING** — decisión explícitamente no tomada; requiere aprobación
  explícita del usuario o un ADR antes de usarse como base de código
  nuevo.
- **NOT IMPLEMENTED** — no hay código que la use, independientemente de
  su estado de aprobación.

## 1. Matriz

| Tecnología | Estado | Motivo |
|---|---|---|
| Python 3.11+ | **APPROVED** | En uso real (`pyproject.toml::requires-python`); todo `src/juval/` está escrito en Python. Originalmente una recomendación técnica no vinculante (`ARCHITECTURE.md` §15), consolidada como hecho por el código existente, no por un ADR de stack. |
| `openpyxl>=3.1` | **APPROVED** | Única dependencia de runtime (`pyproject.toml`); usada en `infrastructure/excel/importer.py` y `exporter.py` para leer/escribir `.xlsx`. |
| `pytest>=7` | **APPROVED** | Única dependencia de desarrollo; ejecuta los 177 tests del repositorio (ver `TESTING_STRATEGY.md`). |
| `dataclasses` (stdlib) | **APPROVED** | Todo el modelo de dominio (`domain/*.py`) y los resultados de `processing/*.py` son `@dataclass(frozen=True)` — sin `pydantic` ni otro framework de modelado. |
| Ponytail (plugin `ponytail@ponytail`) | **APPROVED** (activo) | Instalado y activo en este entorno de agente, modo FULL por defecto (`CLAUDE.md` §5). No es una dependencia del código de Juval — es una herramienta del flujo de trabajo del agente, no aparece en `pyproject.toml` ni se importa desde `src/`. |
| Git / control de versiones | **NOT IMPLEMENTED** | No existe `.git` en este repositorio (verificado: `git status` falla). Decisión pendiente explícita del usuario (`ARCHITECTURE.md` §14.7) — no confundir con "GitHub" (§ siguiente), que es un paso posterior y depende de que exista un repositorio Git local primero. |
| GitHub | **PENDING** | Sin repositorio Git local, no puede haber un remoto en GitHub todavía. Aparece en el `README.md` raíz de Fase 0 solo como parte de la lista de tecnologías candidatas del stack frontend PWA, nunca aprobado por ADR. |
| Next.js | **PROPOSED** | Mencionado como candidato de frontend en `README.md`/`CLAUDE.md` §14 para la futura Fase 4 (Dashboard/PWA). Ningún ADR lo aprueba. No hay una sola línea de código de frontend en el repositorio. |
| Tailwind CSS | **PROPOSED** | Mismo estado y misma razón que Next.js — candidato de Fase 4, sin ADR. |
| Vercel | **PROPOSED** | Candidato de deployment para Fase 4/Fase 10 — la elección de interfaz (PWA) ya está resuelta (ADR-014), pero Vercel específicamente sigue sin ADR ni aprobación. |
| Supabase | **PENDING** | `CLAUDE.md` §14 lo marca explícitamente PENDING: "no introducir hasta necesidad real de persistencia; no crear tablas por si acaso". Bloquea Fase 8 (`PROJECT_PLAN.md`). Ningún código de persistencia existe. |
| Clerk | **PENDING** | `CLAUDE.md` §14: "no implementar mientras el producto funcione sin autenticación". Bloquea Fase 9. Ningún código de autenticación existe. |
| PWA | **APPROVED** (2026-08-17) | Elegida explícitamente por el usuario como interfaz principal de Juval. ADR-014 (`Estado: Aceptada`) documenta la decisión — **no** aprueba ningún framework/hosting concreto para implementarla (ver ADR-014 §"Límites explícitos de esta decisión"). ADR-005 sigue vigente sin modificar (independencia de diseño). |
| `.exe` (Windows, ej. vía PyInstaller) | **NOT CHOSEN** (2026-08-17) | Evaluado junto a PWA (`ARCHITECTURE.md` §10) y no elegido como interfaz principal (ADR-014). No se descarta como técnicamente imposible en el futuro (ADR-005 preserva la independencia de diseño), pero no hay trabajo planeado en esta dirección. |
| FastAPI | **PROPOSED** | Mencionado en `ARCHITECTURE.md` §15 como opción para el backend de la PWA ya elegida (`interfaces/api/`, ADR-014). La elección de interfaz ya no bloquea esto — el framework backend concreto sigue sin ADR, sin código. |
| Typer / argparse | **PROPOSED** | Mencionado en `ARCHITECTURE.md` §15 como opción para un futuro CLI (`interfaces/cli/`, todavía solo `README.md`). Ninguna de las dos librerías está en `pyproject.toml`. |
| PyInstaller | **PROPOSED** | Mencionado junto con `.exe` — sin ADR, sin código. |

## 2. Regla de decisión para agregar cualquier tecnología nueva

Antes de agregar una dependencia (`CLAUDE.md` §20): ¿ya hay código
existente que resuelva esto? ¿lo resuelve la stdlib? ¿lo resuelve una
dependencia ya instalada (`openpyxl`, `pytest`)? ¿hay una solución más
simple sin dependencia nueva? Si se agrega de todas formas, documentar
por qué en el commit y en esta matriz.

Para cualquiera de las filas **PROPOSED** o **PENDING** de §1: no se
trata como base de código nuevo hasta que exista un ADR aceptado o una
instrucción explícita del usuario que la respalde (`CLAUDE.md` §3). Este
documento no constituye esa aprobación por sí mismo — solo la registra
cuando ya ocurrió en otro lugar (ADR, o instrucción directa del usuario
registrada en `docs/PROJECT_PLAN.md`).

## 3. Relacionado

`CLAUDE.md` §14 (fuente normativa de los estados PENDING de Supabase/
Clerk/frontend), ADR-005 (independencia PWA/.exe), `PROJECT_PLAN.md` §4
(tabla de decisiones bloqueantes activas), `ARCHITECTURE.md` §15
(recomendación técnica original, no vinculante).
