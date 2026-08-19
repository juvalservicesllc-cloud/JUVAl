# ADR-023: Gobernanza del Product Experience / Design System (frontend)

- Estado: Aceptada — a petición explícita del usuario, inicio formal del
  rediseño integral de UI/UX de JUVAl ("PREMIUM PRODUCT UI/UX REDESIGN",
  sesión 2026-08-19).
- Fecha: 2026-08-19

## Contexto

El usuario inició un rediseño integral del frontend (`frontend/`) hacia un
estándar SaaS B2B premium (referencia de calidad: Linear/Stripe/Vercel/Ramp,
sin copiar ninguno), ejecutado en fases (Foundation, App Shell, Dashboard,
Catalog, Product Detail, Runs, Appearance/Responsive/A11y/Motion, QA).

El frontend ya tenía un sistema de theming funcional
(`frontend/src/theme/`) con Light/Dark, branding local (logo, accent,
imagen de fondo) vía `localStorage` (`docs/FRONTEND_BACKEND_HANDOFF.md`
§22), y una capa de componentes/CSS hecha a mano (custom properties, sin
Tailwind ni librería de componentes). No existía, hasta ahora, un límite
explícito y documentado entre "qué puede decidir/cambiar la capa de
presentación" y "qué pertenece exclusivamente al dominio/backend".

## Decisión

Se establece una frontera explícita de gobernanza para el Product
Experience:

**El frontend PUEDE evolucionar libremente**: jerarquía visual,
arquitectura de información, navegación, app shell, composición de
página, spacing, tipografía, densidad, tablas, filtros, controles,
charts, patrones de interacción, estados vacíos/carga/error, layout
responsive, accesibilidad, microinteracciones, motion, apariencia
light/dark, identidad visual, design tokens.

**El frontend NO PUEDE redefinir** (solo puede *representar mejor*):
fórmulas financieras (ROI, profit, margin, break-even, max COG),
`BUY`/`REVIEW`/`PASS`, semántica de riesgo (HAZMAT/BULKY, severity),
provenance (`VERIFIED`/`INFERRED`/`NOT_FOUND`/`INVALID`), contratos
backend (`RecordOut`, `RunSummaryOut`, etc.), modelos de dominio,
endpoints. Esto ya estaba implícito en `docs/FRONTEND_BACKEND_HANDOFF.md`
(ownership Codex/Claude Code) y en CLAUDE.md §9/§25 — esta ADR lo hace
explícito también como regla de gobernanza del *design system*, no solo
de la integración API.

Si una superficie necesita un dato que el contrato actual no expone
(ej. `title`/`brand` en `RecordOut`, ya documentado como gap en
`FRONTEND_BACKEND_HANDOFF.md` §15 Priority 2), la UI debe declarar
**BACKEND/DATA GAP** explícitamente y continuar con los datos reales
disponibles — nunca inventar el dato ni simularlo sin una etiqueta
`DEMO_FIXTURE`/`INFERRED` visible.

### Fase A (Foundation + Design System) — cambios aceptados en esta ADR

Dirección visual elegida por el usuario entre 3 alternativas presentadas
(Refined Minimalism / Deep Tech / Warm Enterprise Trust): **Refined
Minimalism**, evolución del sistema existente (mismo acento índigo,
misma estructura Light/Dark) en vez de un reemplazo de identidad.
Tipografía: Inter para UI (sin cambio, ya instalada) + pila monospace
nativa (`ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
"Liberation Mono", monospace`) para datos tabulares/identificadores —
sin nueva dependencia (ponytail: stack nativo cubre el requisito sin
añadir un webfont).

Cambios concretos (`frontend/src/theme/presets.ts`,
`frontend/src/theme/ThemeProvider.tsx`, `frontend/src/App.css`,
`frontend/src/components/ColorControl.tsx`, `frontend/vite.config.ts`,
`frontend/index.html`):

- Paleta dark refinada: grafito más frío (`#14161b`/`#1a1d24`) en vez
  del grafito anterior (`#0c0d10`/`#15171c`); paleta light no invertida
  (`#f7f8fb`/`#ffffff`, texto `#16181d`) en vez del flip anterior.
- Acento índigo refinado: `#6a7bff` (dark) / `#4f5fe0` (light) — misma
  familia de color que el acento anterior (`#7c8cff`), no una identidad
  nueva.
- Semántica BUY/REVIEW/PASS actualizada a `#34c77b`/`#e0a940`/`#e2646c`
  — sigue siendo mode-independent (badges), tal como ya documentaba
  `FRONTEND_BACKEND_HANDOFF.md` §22 ("Status/provenance badge colors
  remain semantic and are not redefined by customer accent
  selections") — esta ADR no cambia esa regla, solo el valor exacto de
  los tres colores.
- `--chart-grid` deja de ser un hex fijo (`#292d36`, ilegible en modo
  claro) y pasa a `color-mix(in srgb, var(--text-primary) 12%,
  transparent)` — se adapta automáticamente al modo sin lógica nueva en
  `ThemeProvider.tsx`.
- Nuevos design tokens fundacionales en `:root` (`--radius-*`,
  `--space-*`, `--font-*`, `--ease`/`--duration-*`) — **declarados,
  no migrados todavía a cada componente**: la migración progresiva
  ocurre fase por fase (B–G) a medida que cada superficie se
  reconstruye, no como un refactor masivo de una sola vez.
- `vite.config.ts`/`index.html`: `theme_color`/`background_color` del
  manifest PWA corregidos de `#0a7d24` (verde, sin relación con la
  marca — valor de plantilla sin usar) a `#14161b`, coherente con el
  grafito dark por defecto.

## Qué NO resuelve esta decisión

- No cambia ningún endpoint, DTO, ni dato consumido — cero cambios en
  `frontend/src/api/`, `frontend/src/types.ts`.
- No migra automáticamente cada valor de spacing/radius hardcodeado en
  `App.css` a los tokens nuevos — eso es trabajo explícito de las Fases
  B–G, no de esta ADR.
- No resuelve el gap conocido de colores hardcodeados no adaptados a
  modo (ej. `.panel-heading a { color:#aeb7ff }`) — queda registrado
  como deuda de diseño a corregir cuando esa superficie se reconstruya.
- No aprueba `title`/`brand` en `RecordOut` ni ningún otro cambio de
  contrato backend — Products sigue `DEMO` hasta que esa decisión de
  backend se tome (`FRONTEND_BACKEND_HANDOFF.md` §15).

## Alternativas consideradas

1. **Reemplazar la identidad visual por completo** (paleta
   navy/esmeralda "Warm Enterprise Trust" o dirección "Deep Tech"):
   descartado por el usuario — evolucionar el índigo existente conserva
   la inversión ya hecha en el customizer de marca (`/appearance`) y es
   reversible con menor riesgo.
2. **Añadir una fuente monospace de marca (ej. JetBrains Mono) vía
   `@fontsource`**: descartado (ponytail) — la pila monospace nativa del
   sistema operativo ya cumple el requisito visual/funcional
   (alineación tabular, distinción de Inter) sin bytes adicionales ni
   dependencia nueva que mantener.
3. **Migrar todo `App.css` a los tokens nuevos en un solo cambio**:
   descartado — el usuario pidió fases incrementales explícitas; un
   refactor masivo de un archivo CSS de alta densidad en Fase A
   contradice esa instrucción y el principio de diff mínimo por fase.

## Impacto

Archivos tocados (todos `frontend/`, cero cambios de backend/dominio):
`frontend/src/theme/presets.ts`, `frontend/src/theme/ThemeProvider.tsx`,
`frontend/src/App.css`, `frontend/src/components/ColorControl.tsx`,
`frontend/src/pages/AppearancePage.test.tsx` (expectativas de color
actualizadas), `frontend/vite.config.ts`, `frontend/index.html`.

Verificado: `npx vitest run` (59/59), `npm run build` (TypeScript +
producción PWA), `npm run lint` (oxlint) — los tres sin errores tras el
cambio. Sin dependencias nuevas, bundle JS sin cambio de tamaño
(642.92 kB, igual que antes), CSS +0.5 kB por los tokens nuevos.

## Consecuencias

- Positivas: existe ahora un límite explícito y citable
  (presentación vs. dominio) para las fases siguientes del rediseño;
  los tokens fundacionales quedan disponibles para que las Fases B–G
  los consuman sin re-derivar valores; el manifest PWA deja de mostrar
  un color de marca incorrecto (`#0a7d24`).
- Negativas: la migración incompleta de spacing/radius a tokens deja el
  sistema en un estado transitorio (tokens definidos, adopción
  parcial) hasta que las fases siguientes toquen cada componente.
- Reversibilidad: alta — son valores de custom properties CSS y un
  archivo de paleta; revertir no requiere tocar dominio, backend, ni
  contratos.

## Relacionado

ADR-014 (PWA), ADR-016 (FastAPI/`interfaces/api`),
`docs/FRONTEND_BACKEND_HANDOFF.md` (ownership Codex/Claude Code,
§22 Appearance/Branding), CLAUDE.md §5 (Ponytail: minimalismo de
implementación, no de arquitectura), §9 (provenance), §25 (flujo de
datos DATA → CALCULATION → RISK → DECISION → AI EXPLANATION, nunca al
revés).
