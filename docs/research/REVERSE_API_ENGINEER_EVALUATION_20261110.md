# Evaluación de Reverse API Engineer y pruebas de conectores — 2026-11-10

- Estado del trabajo: **ADR-057 Aceptada** (2026-11-10). D5 diferida a
  ADR-058 (Propuesta).
- Revisión 2 (2026-11-10): incorpora la aprobación conceptual del propietario
  y corrige tres errores y un conflicto de la revisión 1 (§8).
- Alcance: investigación y diseño. No se modificó código, frontend, backend,
  infraestructura, dependencias ni producción. No se instaló ni ejecutó la
  herramienta evaluada. No se hizo ninguna petición a Amazon, Keepa ni a
  terceros fuera de GitHub y PyPI para leer metadatos y código público.
- Esto no es asesoría legal.

## 0. Conclusión

**No adoptar Reverse API Engineer para JUVAl.** Lo que hace, lo hace de verdad,
pero su diseño se basa en tres cosas que JUVAl prohíbe: credenciales
hardcodeadas, evasión de detección de bots y reutilización de las sesiones
reales del navegador. Además, sus clientes los genera un LLM, así que no son
reproducibles.

**No hace falta un Integration Lab independiente.** Las pruebas de futuros
conectores autorizados se escriben dentro de `tests/`, con los mecanismos
existentes: bloqueo de red, test de imports por AST, fixtures `_TEST_DATA`,
escáner de secretos y provenance de `domain/`. Se crean junto al primer
conector autorizado, no antes. El cuello de botella de JUVAl no es descubrir
APIs: las fuentes candidatas ya publican sus contratos. Lo que falta es
autorización.

El propietario aprobó conceptualmente estas dos conclusiones el 2026-11-10
(ADR-057 §2).

---

## 1. Fase 1 — Investigación de la herramienta

### 1.1 Identificación

No se pudo ver el video. El repositorio se identificó por nombre: es el único
proyecto público llamado "Reverse API Engineer".

| Dato | Valor verificado (API de GitHub, 2026-11-10) |
|---|---|
| Repositorio | `github.com/kalil0321/reverse-api-engineer` (PyPI `reverse-api-engineer`, CLI `rae`) |
| Licencia | MIT |
| Creado / último push | 2025-12-23 / 2026-11-08 |
| Releases recientes | v0.15.0 (2026-11-09), v0.14.0 (09-23), v0.13.1 (08-30), v0.13.0 (07-27), v0.12.0 y v0.11.0 (07-22) |
| Popularidad | 3.332 estrellas, 328 forks, 6 issues abiertos |
| Madurez declarada | `Development Status :: 4 - Beta`, versión 0.x |
| Contribuidores | `kalil0321` con 504 commits. Le siguen bots/agentes (`claude` 14, `cursoragent` 9) y externos con 7 o menos |
| `SECURITY.md` | No existe (404). La API de advisories no devolvió ninguno |

**Mantenimiento:** muy activo, con releases cada 2–6 semanas y un CHANGELOG
cuidado que incluye secciones de seguridad (pins de versiones, CVEs de
dependencias). **Riesgo:** en la práctica depende de una sola persona y es
una versión 0.x con cambios de comportamiento frecuentes. Por ejemplo, en
v0.15.0 cambió el proveedor por defecto a `chrome-mcp`.

### 1.2 Cómo funciona

1. El usuario indica un sitio y un objetivo.
2. Se navega el sitio de una de dos formas:
   - **manual:** una persona usa Playwright, con el extra `[manual]`;
   - **agent:** un agente LLM controla el navegador por `chrome-mcp`,
     Playwright MCP o `agent-browser`.
3. Se captura el tráfico en un HAR (excepto con `chrome-mcp`, que no guarda HAR).
4. Un LLM lee el HAR y escribe un cliente en uno de 10 lenguajes. Por defecto
   usa Claude vía `claude-agent-sdk`; también admite OpenCode, Cursor o Copilot.
5. El comando `run` puede ejecutar el cliente generado e instalar sus
   dependencias con `--auto-install`.

Dependencias base (`pyproject.toml`): `claude-agent-sdk`, `requests`,
`aiohttp`, `httpx2` (de Pydantic; verificado en PyPI), `cryptography`,
`PyJWT`, `starlette`, `rich` y `prompt-toolkit`, entre otras. Extras opcionales:
`playwright` + `playwright-stealth` (manual), `beautifulsoup4` (collector) y
`github-copilot-sdk`. Además, durante la ejecución descarga herramientas con
`npx`/`npm install -g`: `chrome-devtools-mcp`, `rae-playwright-mcp@0.0.9`,
`agent-browser@0` y `opencode-ai@latest`.

### 1.3 Hallazgos de seguridad verificados en el código

| # | Hallazgo | Evidencia | Choca con |
|---|---|---|---|
| S1 | El generador obliga a hardcodear credenciales | `prompts/engineer/system.md`: "Hardcode all credentials, cookies, tokens, and session data found in the traffic. No env vars, no config files". La misma regla aparece en `prompts/auto/system.md` y en los 10 partials de lenguaje | CLAUDE.md §16; `SECRETS.md` |
| S2 | Instrucciones de evasión de bots | `partials/_language_python.md`: "If you encounter bot detection or anti-scraping measures, first try `httpcloak` to cloak your HTTP fingerprint … If `httpcloak` cannot bypass the protection, fall back to … Playwright CDP" | `DATA_SOURCES.md` §2 |
| S3 | Navegador "stealth" | `browser.py` importa `playwright_stealth` e inyecta `STEALTH_JS` para ocultar `navigator.webdriver` y otras señales ("bypasses common detection methods") | `DATA_SOURCES.md` §2 |
| S4 | Acceso a las sesiones reales del usuario | `chrome-mcp` (por defecto desde v0.15.0) controla el Chrome real "with their existing sessions, cookies, and authentication" | El alcance del agente incluiría Seller Central, correo, FusionAuth admin, etc. |
| S5 | El HAR y sus secretos se envían al LLM | El HAR completo es la entrada del modelo. Por defecto va a la API de Anthropic; con OpenCode, Copilot o Cursor va a otros proveedores | CLAUDE.md §16 (no exponer tokens) |
| S6 | Cadena de suministro en tiempo de ejecución | `npm install -g`/`npx -y` de paquetes externos, `opencode-ai@latest` sin versión fija y `--auto-install` de dependencias del código generado | Política de dependencias §20 |
| S7 | Ejecuta código generado | El propio README dice: "Generated code runs locally … review before executing" | Regla de no ejecutar contenido no revisado |

Puntos a favor, también verificados: v0.15.0 aísla la sesión de Claude de la
configuración del usuario (no carga `CLAUDE.md`, hooks ni MCP), fija la versión
del MCP de Playwright y sube los mínimos de seguridad de varias dependencias.
El `SKILL.md` pide "Only capture sites the user is allowed to access, and
respect their terms and rate limits" y no pegar HARs en issues. Esa
advertencia vive en la documentación, pero los prompts de generación hacen
lo contrario (S1 y S2).

### 1.4 Capacidades demostradas frente a afirmaciones promocionales

| Afirmación | Valoración |
|---|---|
| Captura HAR desde navegador manual o agente | **Demostrado en código** (`browser.py`, prompts de agente) |
| Genera clientes en 10 lenguajes | **Demostrado en código** (partials por lenguaje y runner por lenguaje). La calidad depende del modelo |
| "Live client validation" | **Parcialmente demostrado.** v0.14.0 añade un test opcional contra una API *fixture* propia, no contra sitios reales |
| "Reverse engineer any website" | **Promocional.** El README reconoce: "Sites with aggressive bot detection may block capture" |
| "Typed client" | **Depende del LLM.** No hay generación a partir de esquema ni validación de tipos contra un contrato |
| "Works immediately with zero user effort" | **Logrado precisamente con S1:** funciona porque incrusta tokens de sesión, que caducan o quedan expuestos |
| Clientes **reproducibles** | **No.** La salida es de un LLM: el mismo HAR puede producir clientes distintos. No hay versión de esquema ni hash de contrato. Existe `/resume` de la conversación, pero eso no hace determinista la salida |
| Descubrimiento de endpoints | **Sí, limitado a lo observado.** Solo ve el tráfico que el navegador generó en esa sesión, sin cobertura de errores, paginación ni límites no ejercitados |

---

## 2. Fase 2 — Auditoría de JUVAl (solo lectura)

### 2.1 Importación y procesamiento hoy

- Flujo implementado: `infrastructure/excel/importer.py::import_file`
  (`.xlsx`/`.csv`) → `processing/pipeline.py::process_batch` →
  `application/run_pipeline.py`. El resultado es un `ExecutionRun` más
  `SourcingRecord`s.
- La única fuente de datos real es el archivo del proveedor (`SUPPLIER_FILE`).
- `infrastructure/enrichment/` solo contiene `README.md`.

### 2.2 Interfaces existentes para integrar proveedores

- **No hay un puerto de enriquecimiento implementado.** Los `Protocol`
  existentes en `application/` son todos de persistencia o sesión:
  `ExecutionRunStore`, `RecordSnapshotStore`, `BatchStore`, `SessionStore`,
  `FinancialRecordStore`, `ReportStore` e `IdentityPasswordPort`. Ese es el
  patrón a seguir: el puerto se define hacia adentro y el adapter vive en
  `infrastructure/`.
- **Contrato de puerto ya diseñado** (no implementado):
  `ProductCatalogSource.search_by_identifiers(marketplace, identifier_type,
  identifiers)` en `DATA_ACQUISITION_MATRIX.md` §17. Incluye batch ≤ 20,
  respeta `x-amzn-RateLimit-Limit` y define los tests requeridos (match
  exacto, cero, múltiples, respuesta malformada, fallo, provenance y split
  20/21).
- **Contratos de dominio para lo que devuelva un proveedor:** las
  observaciones de ADR-046 (`domain/market_evidence.py`: `DemandObservation`,
  `CompetitionCount`, `PriceObservation`, `PriceSeries`, ...), con el patrón
  de ADR-052 de transportarlas fuera de `Product`.

### 2.3 Compatibilidad

| Componente | Compatibilidad con un conector autorizado | Con un cliente de rae |
|---|---|---|
| Provenance (`domain/provenance.py`) | Directa: `SourceType.OFFICIAL_API` o `AUTHORIZED_EXTERNAL_SOURCE`, `retrieved_at` real y `source_reference` igual al id de la petición | **Incompatible.** Un endpoint no documentado y obtenido por captura no es `OFFICIAL_API` ni `AUTHORIZED_EXTERNAL_SOURCE`, y no hay un `SourceType` para ello (por diseño) |
| Estados de verificación (ADR-004) | La taxonomía 429/5xx/auth/malformado ≠ `NOT_FOUND` ya está fijada (`DATA_SOURCES.md` §1b) | Los clientes generados no distinguen esos casos de forma controlada |
| Decision Engine | Sin cambios. Las observaciones nuevas no alimentan `DecisionInputs` sin un ADR de proyección (ADR-052 §20.3) | Igual, pero el dato de origen no sería admisible |
| ExecutionRun | **Hueco conocido:** no registra `sources_used` ni la configuración (CLAUDE.md §15). ADR-051 (Propuesta) cubriría la configuración (umbrales, fees, política), **no** las fuentes. Un conector activo empeoraría la reproducibilidad hasta que exista una decisión propia | Peor: el cliente cambia entre generaciones |
| Capas (ADR-001) | Adapter en `infrastructure/enrichment/` y puerto hacia adentro | Código generado y autónomo, sin puerto |
| Secretos (`SECRETS.md`, clase 2) | Variables de entorno solo en backend, con rotación ≤ 12 meses | Hardcodeados en el código fuente |

---

## 3. Fase 3 — Diseño: pruebas de contrato de conectores en `tests/`

La revisión 1 proponía un "Integration Lab" independiente en `lab/integration/`.
Se retira (§8, E2). El propietario aprobó conceptualmente reutilizar la
infraestructura de pruebas existente. `tools/integration_lab.py`, el entorno
OIDC local de SEC-01F, no tiene relación con esto y no se toca.

### 3.1 Principios

- No se crea ningún módulo, directorio, herramienta ni comando nuevo.
- Nada se implementa ahora. Las pruebas llegan con el primer conector
  autorizado, dentro de su propio cambio.
- Ninguna prueba accede a la red, usa credenciales reales ni descarga
  especificaciones.
- Frontera de imports bidireccional:
  - las pruebas pueden importar `juval.domain` y el adapter bajo prueba;
  - no importan `interfaces/` ni otras partes de `infrastructure/`;
  - el código de producción nunca importa `tests/`.
- No se crean adapters ficticios ni de referencia (ADR-046 §15). Los fixtures
  son datos de test y los dobles de transporte viven solo dentro de los tests.

### 3.2 Requisito → mecanismo existente

| Requisito | Mecanismo existente |
|---|---|
| Sin red | Bloqueo de `socket.connect`, `connect_ex` y `create_connection` (patrón de `tests/unit/test_gate_b2_evidence.py`) |
| Sin importar capas prohibidas | Test de imports por AST (patrón de `tests/unit/test_financial_calculation.py`) |
| Datos sintéticos | `tests/fixtures/`, convención `_TEST_DATA` |
| Sin credenciales ni secretos | `tools/compliance_check.py` (escanea `.py` y `.json` de `tests/`); `SECRETS.md` §6 |
| Validación de esquema | Parser con dataclasses y stdlib. Un campo obligatorio ausente o un tipo incorrecto es fallo de esquema, nunca `NOT_FOUND` |
| Contrato fijado | Especificación oficial aportada o aprobada por el propietario, fijada por SHA-256 (`hash_file`) |
| Provenance | `FieldValue`, `Provenance` y `combine_verification_status` reutilizados, sin duplicar |
| Evidencia de mercado | Value objects de ADR-046 sin cambios; sin proyección a `Product` ni `DecisionInputs` (ADR-052 §20.3) |
| Errores | 429, 5xx, timeout, auth y malformado ≠ `NOT_FOUND` (`DATA_SOURCES.md` §1b) |
| Reproducibilidad | `pytest` con `pythonpath = ["src"]`; sin dependencias nuevas |
| Aprobación humana | Registro en `DATA_SOURCES.md` §5 o en un ADR. Deshabilitado por defecto, flag explícito y fallo al arrancar (`SECURITY.md` §3, patrón ADR-055) |

Los casos de prueba mínimos son los de `DATA_ACQUISITION_MATRIX.md` §17, más
las comprobaciones de esquema, errores, provenance, bloqueo de red y frontera
de imports (ADR-057 §3).

## 4. Fase 4 — Informe

### 4.1 Evaluación técnica y arquitectónica

- Técnicamente, rae es un proyecto serio, activo y con buenas prácticas de
  release. Para su caso de uso (cliente rápido de un sitio que el usuario
  controla) funciona.
- Arquitectónicamente no encaja en JUVAl:
  - genera código autónomo, no adapters detrás de un puerto;
  - su contrato es tráfico observado, no una especificación;
  - su salida no es reproducible;
  - su forma de lograr "zero effort" es incrustar secretos.
- Las fuentes que JUVAl necesita (SP-API y un proveedor histórico con licencia)
  publican contratos. Amazon publica los modelos OpenAPI de SP-API en
  `github.com/amzn/selling-partner-api-models`. Esto hace innecesario el
  descubrimiento por ingeniería inversa.

### 4.2 Riesgos

**Legales** (no es asesoría legal):

- Las Condiciones de Uso de Amazon prohíben robots y data mining en sus sitios.
- Las políticas de SP-API (Acceptable Use, DPP) son las que Amazon revisa en
  el caso de remediación pendiente (`compliance/SP_API_REGISTRATION_REMEDIATION.md`).
  Usar scraping o evasión podría comprometer esa solicitud.
- Los ToS de Keepa y SellerAmp no autorizan extracción de su web; SellerAmp
  está marcado como "no integrar, no scrapear" (`DATA_ACQUISITION_MATRIX.md` §6).
- La evasión de controles técnicos (S2, S3) añade riesgo propio en varias
  jurisdicciones.

**De seguridad:** S1–S7 (§1.3). El más grave es S4 combinado con S5: un agente
con acceso a las sesiones reales del operador, cuyo tráfico se envía a un LLM
externo.

**Operativos:**

- Clientes que se rompen sin aviso cuando el sitio cambia.
- Tokens que caducan.
- Bus factor de 1 en el proyecto upstream.
- Coste de LLM por cada regeneración.
- Imposibilidad de auditar por qué un cliente hace lo que hace.

### 4.3 Comparación con conectores escritos a mano

| Criterio | rae (HAR + LLM) | Adapter manual desde spec oficial |
|---|---|---|
| Base contractual | Tráfico observado en una sesión | Especificación versionada del proveedor |
| Reproducibilidad | Baja (salida de LLM) | Alta (código revisado, spec fijada por hash) |
| Secretos | Hardcodeados | Variables de entorno en backend |
| Provenance | Ninguna | `FieldValue`/`Provenance` nativos |
| Errores y rate limits | Lo que el LLM decida | Política explícita y probada |
| Legalidad | Depende del sitio; prácticas de evasión incluidas | Dentro del acuerdo del proveedor |
| Velocidad del primer prototipo | Minutos u horas | Días |
| Mantenimiento | Regenerar ante cada cambio | Cambios guiados por changelog de la API |
| Encaje con ADR-001 | Nulo | Directo |

### 4.4 Estimación de costo y esfuerzo

Son estimaciones de orden de magnitud, sin medir. No incluyen precios de
proveedores, que siguen sin ser públicos (`DATA_ACQUISITION_MATRIX.md` §8).

| Trabajo | Esfuerzo estimado | Coste externo |
|---|---|---|
| Corrección documental de ADR-057 (revisión 2) | Horas; ya hecho | 0 |
| Pruebas de contrato del primer conector, cuando se autorice | 0,5–1 día-persona, sumado al del adapter | 0 |
| Adapter SP-API Catalog con su puerto, cuando se autorice | 3–5 días-persona | Coste de SP-API **no público** |
| Activación real | Bloqueada: autorización de Amazon y D5 | — |
| Integration Lab independiente (revisión 1) | **Retirado** | — |
| Experimento con Reverse API Engineer (D6 de la revisión 1) | **Retirado** | — |
| Adoptar Reverse API Engineer | No se adopta | — |

### 4.5 ADR propuesto

`docs/adr/ADR-057-integration-lab-reverse-api-engineer.md`, **Propuesta,
revisión 2.** El nombre del archivo se conserva por trazabilidad; ver
ADR-057 §8.

### 4.6 Plan sin acceso a producción ni a servicios externos

No hay prueba de concepto que ejecutar ahora: sin una fuente autorizada no
existe nada real que probar, y crear un adapter de prueba contradiría
ADR-046 §15. El plan queda así:

1. **Ahora:** solo la revisión de ADR-057 (revisión 2) por el propietario.
2. **Cuando haya una fuente autorizada y D3–D5 aprobadas:**
   - el propietario aporta o aprueba la especificación oficial;
   - se registra la ficha en `DATA_SOURCES.md` §4;
   - en un mismo cambio se implementan el puerto, el adapter en
     `infrastructure/enrichment/` y sus pruebas en `tests/`, siguiendo §3;
   - todo sin red y con fixtures sintéticos.
3. **Para habilitarlo:** aprobación humana registrada, credenciales emitidas
   por el proveedor solo en el backend y la decisión de D5.

Criterio de aceptación para ese cambio futuro:

- la suite completa pasa sin red ni credenciales;
- cada valor conserva su provenance;
- ningún fallo operacional se convierte en `NOT_FOUND`;
- el escáner de secretos y el test de imports quedan limpios;
- no se añaden dependencias;
- `processing/` y el motor de decisión no cambian.

---

## 5. Decisiones

| ID | Decisión | Estado |
|---|---|---|
| D1 | No adoptar Reverse API Engineer | **APROBADA** (2026-11-10) |
| D2 | Sin lab independiente: pruebas dentro de `tests/` (sustituye a `lab/integration/`) | **APROBADA** |
| D3 | Contrato solo desde especificación oficial o entregada bajo acuerdo, con identificación y conservación verificable | **APROBADA** (ADR-057 §4 D3.1–D3.4) |
| D4 | Validación con biblioteca estándar; excepciones solo justificadas y acotadas | **APROBADA** (ADR-057 §4 D4.1–D4.4) |
| D5 | Registro de fuentes por `ExecutionRun` (ADR-051 no lo cubre) | **DIFERIDA** a ADR-058 (Propuesta) |
| D6 | Experimento con Reverse API Engineer | **RETIRADA DEFINITIVAMENTE** |

ADR-057 quedó **Aceptada** el 2026-11-10.
| — | Prohibición de scraping, evasión y exposición de credenciales | **APPROVED** (`DATA_SOURCES.md` §2, `SECRETS.md` §2; confirmada por el propietario) |

## 6. Pendientes / FUTURE

- Generador OpenAPI determinista: evaluar solo si el número de operaciones
  lo justifica.
- `jsonschema` como dependencia: decisión aparte.
- Registro de las fuentes usadas por `ExecutionRun` (D5): requiere ampliar
  ADR-051 o un ADR propio; ADR-051 no lo cubre.
- Remediación del perfil de desarrollador SP-API: sigue siendo el bloqueo
  real para cualquier dato externo.

## 7. Fuentes

- Repositorio: <https://github.com/kalil0321/reverse-api-engineer>. Se leyeron
  en `main` el 2026-11-10: `README.md`, `pyproject.toml`, `CHANGELOG.md`,
  `src/reverse_api/browser.py`, `src/reverse_api/prompts/**` y
  `skills/reverse-api-engineer/SKILL.md`.
- API de GitHub: metadatos, releases, contribuidores, commits, issues y
  advisories del repositorio (2026-11-10).
- PyPI: <https://pypi.org/project/reverse-api-engineer/> y
  <https://pypi.org/project/httpx2/>.
- Artículo del autor: <https://dev.to/kalil0321/reverse-engineering-undocumented-apis-with-claude-1l33>.
- Directorios de terceros (sin autoridad, solo para identificar el repo):
  everydev.ai, skills.sh, claudemarketplaces.com.

## 8. Correcciones de la revisión 2

| # | Error o conflicto de la revisión 1 | Dónde estaba | Corrección |
|---|---|---|---|
| E1 | Se atribuyó a ADR-051 el registro de fuentes por corrida. ADR-051 P1 solo cubre umbrales, fees, política, severidad, calidad y opciones ADR-047 | §2.3, §5; ADR-057 D5 | D5 exige una decisión propia o una ampliación de ADR-051 |
| E2 | Se propuso `lab/integration/` sin inventariar `tests/`. El nombre "Integration Lab" colisiona con `tools/integration_lab.py` | §0, §3, §4.4–§4.6; ADR-057 D2 | Sin módulo nuevo; pruebas en `tests/` |
| E3 | El plan se presentaba "sin acceso externo", pero descargaba la especificación desde GitHub y ejecutaba Reverse API Engineer (LLM externo, `npx`). Además, la frontera de imports solo fijaba una dirección | §4.6; ADR-057 D6 | La especificación la aporta o aprueba el propietario; D6 retirada; frontera bidireccional |
| C1 | Un adapter de lab construido contra fixtures contradecía ADR-046 §15 ("no se añaden … adapters ficticios") | §3, §4.6 | Solo fixtures y dobles internos de tests; ningún adapter salvo el real autorizado |

Las secciones 1 (investigación), 2.1–2.2 y 4.1–4.3 no cambian.
