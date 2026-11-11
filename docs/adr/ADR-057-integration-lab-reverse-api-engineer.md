# ADR-057 — No adopción de Reverse API Engineer y pruebas de contrato de conectores

- Estado: **Aceptada** (2026-11-10), por decisión explícita del propietario:
  - D1 y D2 aprobadas;
  - D3 aprobada con la precisión sobre identificación y conservación
    verificable de especificaciones;
  - D4 aprobada con excepciones justificadas;
  - D5 diferida a ADR-058;
  - D6 retirada definitivamente.
- Implementación: **no aplica todavía.** El ADR es normativo para futuros
  conectores. No hay cambios de código, dependencias, tests, infraestructura
  ni producción.
- Historial: revisión 1 → revisión 2 (correcciones E1–E3 y C1, §7) →
  revisión 3 (resolución de D1–D6) → aceptación con precisiones de D3 y D4.
- Evidencia: `docs/research/REVERSE_API_ENGINEER_EVALUATION_20261110.md`.
- Nombre de archivo: conserva `…integration-lab…` por trazabilidad (§8). **No**
  propone ningún "Integration Lab". El único entorno con ese nombre es
  `tools/integration_lab.py` (SEC-01F, `LOCAL_INTEGRATION_ENVIRONMENT.md`),
  que este ADR no toca.
- Relacionados, sin modificarlos: ADR-001, ADR-003, ADR-004, ADR-006, ADR-046,
  ADR-051 (Propuesta), ADR-052, ADR-055; `DATA_SOURCES.md` §1b, §2 y §4;
  `DATA_ACQUISITION_MATRIX.md` §8 y §17; `compliance/SECRETS.md`.

## 1. Contexto

Se evaluó `kalil0321/reverse-api-engineer` (MIT, v0.15.0). La herramienta
captura tráfico de navegador (HAR) y un LLM genera un cliente. En su código
fuente se verificó lo siguiente (2026-11-10):

- Los prompts de generación ordenan "Hardcode all credentials, cookies,
  tokens, and session data … No env vars, no config files".
- El prompt para Python indica camuflar la huella HTTP con `httpcloak` y, si
  no basta, hacer las peticiones a través del navegador vía CDP.
- El modo manual usa `playwright-stealth` y un JS propio para ocultar señales
  de automatización.
- El proveedor de agente por defecto (`chrome-mcp`) controla el Chrome real
  del usuario, con sus sesiones.

Esto contradice `DATA_SOURCES.md` §2 y CLAUDE.md §13 y §16. Las fuentes
candidatas de JUVAl (SP-API, proveedor histórico con licencia) publican
contratos oficiales. Lo que bloquea es la autorización (SP-API: NOT ELIGIBLE),
no descubrir endpoints.

## 2. Principios aprobados por el propietario (2026-11-10)

1. No adoptar Reverse API Engineer como dependencia ni herramienta de JUVAl.
2. No crear un Integration Lab independiente.
3. Reutilizar la infraestructura de pruebas existente para futuras pruebas de
   conectores autorizados.
4. Mantener las prohibiciones de scraping no autorizado, evasión de controles
   y exposición de credenciales (`DATA_SOURCES.md` §2, `SECRETS.md` §2).

Las decisiones concretas y su estado final están en §4.

## 3. Diseño: pruebas de contrato de conectores dentro de `tests/`

No se crea ningún directorio, módulo, herramienta ni comando nuevo. **Nada se
crea ahora.** Las pruebas aparecen junto al primer conector autorizado, como
parte de su propio cambio.

| Necesidad | Mecanismo existente que se reutiliza |
|---|---|
| Sin red | Fixture que bloquea `socket.connect`, `connect_ex` y `create_connection` (patrón de `tests/unit/test_gate_b2_evidence.py`) |
| Frontera de imports | Test por AST de imports (patrón de `tests/unit/test_financial_calculation.py`) |
| Datos sintéticos | `tests/fixtures/`, con la convención `_TEST_DATA` en el nombre |
| Sin secretos | `tools/compliance_check.py`, que ya escanea `.py` y `.json` de `tests/` |
| Ejecución reproducible | `pytest` con `pythonpath = ["src"]`; sin dependencias nuevas |
| Provenance | `FieldValue`, `Provenance` y `combine_verification_status` de `domain/provenance.py`, reutilizados y nunca duplicados |
| Evidencia de mercado | Value objects de ADR-046 (`domain/market_evidence.py`), sin cambios |

Frontera de imports. Las pruebas de un conector pueden importar `juval.domain`
(puro, sin E/S) y el adapter bajo prueba. Nunca importan `interfaces/`, otras
partes de `infrastructure/` ni credenciales del entorno. El código de producción
nunca importa nada de `tests/`.

Contenido mínimo de las pruebas del primer conector:

1. **Esquema:** un payload con un campo obligatorio ausente o un tipo
   incorrecto produce un fallo de esquema. Nunca un valor inventado ni un
   `NOT_FOUND`.
2. **Fallos operacionales:** 429, 5xx, timeout, auth y malformado nunca
   producen `NOT_FOUND` (`DATA_SOURCES.md` §1b).
3. **Provenance de cada valor:**
   - `source_type` `OFFICIAL_API` o `AUTHORIZED_EXTERNAL_SOURCE`;
   - `retrieved_at` con zona horaria;
   - `method` que identifica la operación y la versión del contrato;
   - `source_reference` cuando la fuente lo ofrece.
4. **Observaciones:** las de mercado cumplen ADR-046 sin promoción de estados.
   No se proyectan a `Product` ni a `DecisionInputs` (ADR-052 §20.3).
5. **Casos de `DATA_ACQUISITION_MATRIX.md` §17:** match exacto, cero, múltiples
   candidatos, respuesta malformada, fallo de fuente, batch de 20 y división
   en 21.
6. **Entorno controlado:** el bloqueo de red está activo y la frontera de
   imports se respeta.

Los fixtures se construyen a partir de la especificación oficial que el
propietario aporte o apruebe, fijada por SHA-256 (`hash_file`). Ningún test la
descarga. Un helper compartido entre conectores solo se extrae cuando exista un
segundo conector.

### 3.1 Dobles de transporte

Un **doble de transporte** sustituye en un test la capa que enviaría la
petición HTTP: devuelve un fixture sintético o simula un 429, un 5xx, un
timeout o una respuesta malformada. Solo se admite bajo estas condiciones:

1. Vive exclusivamente en `tests/`, en el archivo de test o en un `conftest.py`.
2. Nunca está en `src/`, nunca se registra como fuente, ni se selecciona por
   configuración, ni se puede habilitar en ningún entorno.
3. Se inyecta en el adapter real bajo prueba. Nunca sustituye al adapter ni
   produce `FieldValue` por su cuenta.
4. Sus datos están marcados como sintéticos (`_TEST_DATA`). No se presentan como
   evidencia comercial ni como datos de Amazon (ADR-046 §18.17).

**Nota de implementación (2026-11-11).** Para probar la maquinaria
reutilizable de conectores antes de que exista un proveedor autorizado, el
propietario ordenó implementarla con fixtures sintéticos. Las pruebas usan
una *definición de operación* sintética (`tests/unit/acquisition_synthetic.py`):
un contrato de pocos bytes escrito para los tests, el host reservado
`.invalid` y valores siempre INFERRED con evidencia sintética explícita. Vive
solo en `tests/`, no se registra como fuente y no es un adapter de producción.
`tests/unit/test_acquisition_boundaries.py` comprueba que nada de ello aparece
en `src/`. **Ratificado por el propietario el 2026-11-11**, exclusivamente
dentro de `tests/`; D1–D6 no cambian.

Compatibilidad con ADR-046 §15 ("no se añaden … adapters ficticios"). Un doble
de transporte no es un adapter: no traduce evidencia al dominio ni existe fuera
de los tests. Este diseño no crea adapters de prueba, de referencia ni de
demostración. El único adapter será el real y autorizado, en
`infrastructure/enrichment/`.

## 4. Decisiones

Estados finales según la resolución del propietario del 2026-11-10.

**D1 — No adopción de Reverse API Engineer. Estado: APROBADA.**
JUVAl no adopta Reverse API Engineer como dependencia, herramienta de
desarrollo ni generador de conectores. Tampoco adopta otras herramientas que
generen clientes con un LLM a partir de tráfico capturado (HAR). No se
instala, ejecuta, vendoriza ni bifurca en ningún entorno del proyecto.

**D2 — Sin Integration Lab independiente. Estado: APROBADA.**
No se crea ningún módulo, directorio, herramienta ni comando de laboratorio
para conectores. Las pruebas de un conector autorizado se escriben en `tests/`
con la infraestructura existente (§3) y se crean dentro del mismo cambio que
introduce ese conector, nunca antes. Los dobles de transporte se rigen por
§3.1. `tools/integration_lab.py` (SEC-01F) no está afectado. Sustituye a la D2
de la revisión 1 (`lab/integration/`), que queda retirada.

**D3 — Origen, identificación y conservación verificable del contrato de un
conector. Estado: APROBADA.**

> **D3.1 Origen.** El contrato de datos de un conector —endpoints,
> parámetros, esquemas de petición y respuesta, códigos de error, límites de
> tasa y tamaño de batch— se toma exclusivamente de una de estas fuentes:
>
> **(a)** la especificación o documentación técnica publicada por el propio
> proveedor para ese acceso;
>
> **(b)** una especificación entregada por el proveedor a JUVAl bajo un
> acuerdo vigente que autorice su uso.
>
> Nunca se deriva de tráfico capturado (HAR, proxy, herramientas de
> desarrollo del navegador), de ingeniería inversa de clientes o
> aplicaciones, de documentación no oficial de terceros ni de la salida de un
> LLM.
>
> **D3.2 Identificación.** Cada documento de contrato se identifica con estos
> campos, registrados en la ficha del conector (`DATA_SOURCES.md` §4) antes
> de escribir código:
>
> | Campo | Contenido |
> |---|---|
> | `contract_id` | Identificador estable: `<proveedor>/<API>/<operación o modelo>` |
> | `origin` | `PUBLISHED` (D3.1 a) o `AGREEMENT` (D3.1 b) |
> | `publisher` | El proveedor que publica o entrega el documento |
> | `version` | Versión declarada por el proveedor; si no declara ninguna, la fecha de publicación que indique el documento. Nunca se inventa una versión |
> | `location` | URL canónica del proveedor (a) o referencia del acuerdo (b), sin credenciales ni tokens en la URL |
> | `obtained_at` | Instante de obtención, con zona horaria |
> | `obtained_by` | Rol de quien lo obtuvo (no credenciales) |
> | `sha256` | Hash de los bytes exactos conservados |
> | `media_type` | Formato del documento (p. ej. JSON OpenAPI, PDF) |
> | `approved_by` / `approved_at` | Aprobación del propietario |
>
> **D3.3 Conservación verificable.**
> - Se conserva una copia de los bytes exactos cuyo SHA-256 figura en la
>   ficha. El hash se recalcula sobre esa copia; si no coincide, el contrato
>   se considera no verificado y el conector no puede habilitarse.
> - **(a) Publicado:** la copia se guarda en el repositorio solo si su
>   licencia permite la redistribución, y en ese caso se registra la
>   licencia.
> - **(b) Acuerdo, o (a) sin permiso de redistribución:** la copia se guarda
>   fuera de Git, en un almacenamiento controlado por el propietario. En el
>   repositorio solo constan los campos de D3.2 y la ubicación lógica de la
>   copia, sin contenido confidencial ni credenciales.
> - La ubicación concreta en el repositorio para (a) se decide con el primer
>   conector. No se crea ningún directorio ahora.
> - Los fixtures sintéticos de `tests/` declaran el `contract_id` y el
>   `sha256` del que derivan.
> - Ningún test descarga el documento.
> - El `method` de la provenance de un valor identifica la operación y el
>   `sha256` del contrato usado (§3).
>
> **D3.4 Cambios y lagunas.**
> - Un cambio de versión o de hash del contrato es un cambio nuevo y
>   explícito: actualiza la ficha, conserva el documento anterior para
>   auditar corridas pasadas y actualiza los fixtures en el mismo cambio.
> - Si la especificación no cubre un comportamiento, se trata como
>   desconocido y se documenta como limitación. No se rellena con
>   suposiciones.

**D4 — Validación con biblioteca estándar y excepciones justificadas.
Estado: APROBADA.**

> **D4.1 Regla.** La validación mínima de las respuestas de un conector
> (presencia de campos obligatorios, tipos, enumeraciones, formatos y rangos
> que exige el contrato) se implementa con la biblioteca estándar de Python y
> dataclasses, siguiendo el estilo de las invariantes de `domain/`.
>
> Un fallo de validación es un fallo de esquema (`DATA_SOURCES.md` §1b).
> Nunca produce `NOT_FOUND`, un valor por defecto ni un valor corregido.
>
> **D4.2 Cuándo se admite una excepción.** Solo cuando la validación manual
> obligaría a reimplementar un validador general. Por ejemplo, cuando el
> contrato oficial usa en las respuestas validadas composiciones de esquema
> (`allOf`/`oneOf`/`anyOf`), referencias recursivas o formatos que la stdlib
> no cubre de forma razonable. La comodidad o la menor cantidad de código no
> justifican una excepción.
>
> **D4.3 Justificación escrita obligatoria**, en el orden de CLAUDE.md §20:
> 1. por qué no basta el código existente;
> 2. por qué no basta la biblioteca estándar;
> 3. por qué no basta una dependencia ya instalada;
> 4. si existe una solución más simple.
>
> Además debe incluir:
> - la licencia, el mantenimiento y las vulnerabilidades conocidas;
> - el tamaño, las dependencias transitivas y el alcance de uso;
> - el plan de fijación de versión.
>
> **D4.4 Condiciones de uso de una dependencia aprobada:**
> - El propietario la aprueba de forma explícita.
> - Se declara en un extra opcional de `pyproject.toml` (como `postgres`),
>   con un comentario que explica su motivo. Nunca se declara en las
>   dependencias base.
> - Solo se importa desde el adapter en `infrastructure/enrichment/`.
>   `domain/` y `processing/` nunca la importan.
> - Opera en modo estricto: sin coerción de tipos, sin rellenar valores por
>   defecto, sin eliminar campos desconocidos sin registrarlo.
> - Sus errores se traducen a fallo de esquema y no se expone su mensaje
>   crudo si puede contener datos de la respuesta.
> - Las pruebas de D2 cubren su comportamiento con los mismos fixtures.

**D5 — Registro de fuentes por corrida. Estado: DIFERIDA a ADR-058
(Propuesta).**
Este ADR no lo decide. Ningún conector externo puede pasar a habilitado hasta
que ADR-058, o la decisión que lo sustituya, esté aceptado e implementado.
ADR-051 no cubre ese registro: solo trata la configuración de decisión.
ADR-058 es independiente y no modifica ADR-051.

**D6 — Experimento con Reverse API Engineer. Estado: RETIRADA
DEFINITIVAMENTE.**
No se ejecuta Reverse API Engineer en ningún entorno, ni siquiera contra una
API local o sintética.

**Condiciones de habilitación de un conector (patrones ya aprobados, no
decisiones nuevas):**
- deshabilitado por defecto y activado solo con un flag explícito;
- una configuración incompleta es un error de arranque, no un modo degradado
  (`SECURITY.md` §3, patrón de ADR-055);
- credenciales solo en variables de entorno del backend (`SECRETS.md`, clase 2);
- aprobación humana registrada en `DATA_SOURCES.md` §5 o en un ADR;
- ADR-058 aceptado e implementado (D5);
- contrato verificado según D3.3 (hash coincidente).

## 5. Consecuencias

- **No cambian:** el código, los tests, las dependencias, el motor de
  decisión, la provenance ni la evidencia de mercado.
- **Retirado:** el trabajo estimado en la revisión 1 para crear el lab
  (1–2 días).
- **Sin efecto en el calendario:** este ADR no desbloquea ninguna fuente. El
  enriquecimiento externo sigue bloqueado por la autorización de SP-API y
  por D5.
- **Coste aceptado:** los conectores se escriben a mano a partir de contratos
  oficiales, con más esfuerzo inicial que un generador.

## 6. Alternativas consideradas

| Alternativa | Motivo de rechazo |
|---|---|
| Adoptar Reverse API Engineer | Secretos hardcodeados, evasión de bots, sesiones reales del navegador, salida no reproducible |
| Fork sin stealth ni hardcode | Sigue derivando el contrato de tráfico observado. Mantener un fork de un proyecto 0.x con un solo mantenedor |
| Integration Lab independiente (revisión 1) | Arquitectura nueva sin necesidad; `tests/` ya cubre red, imports, secretos y fixtures. Colisión de nombre con `tools/integration_lab.py` |
| Generador OpenAPI determinista | Viable si crece el número de operaciones. Hoy el puerto mínimo cubre una. **FUTURE / PENDING** |

## 7. Correcciones respecto de la revisión 1

| # | Error de la revisión 1 | Corrección |
|---|---|---|
| E1 | Se atribuyó a ADR-051 el registro de las fuentes usadas por corrida (D5). ADR-051 P1 no incluye `sources_used` | D5 exige una decisión propia o una ampliación de ADR-051 |
| E2 | Se propuso `lab/integration/` sin inventariar la infraestructura existente. El nombre "Integration Lab" colisiona con `tools/integration_lab.py` | Sin módulo nuevo; pruebas dentro de `tests/` (§3) |
| E3 | El plan se presentó como "sin acceso externo", pero incluía descargar la especificación desde GitHub y ejecutar Reverse API Engineer (LLM externo, `npx`). Además, la frontera de imports solo fijaba una dirección | La especificación la aporta o aprueba el propietario; D6 retirada; frontera bidireccional (§3) |
| C1 | Conflicto con ADR-046 §15: un "adapter de lab" equivale a un adapter ficticio | Solo existirán fixtures y dobles internos de tests; ningún adapter que no sea el real (§3) |

## 8. Puntos abiertos (no bloquean la aceptación)

- **Documentación derivada.** `DATA_SOURCES.md` §4 debería remitir a D3.2 al
  registrar la primera ficha, y CLAUDE.md §18 no incluye ADR-057 en su lista
  de estados. Ninguno se ha modificado; queda como pendiente.
- **Nombre de archivo.** Contiene `integration-lab`. Se conserva
  temporalmente por instrucción del propietario: `frontend-next/BFF_INTEGRATION_REPORT.md`
  (sesión concurrente, sin seguimiento en Git) lo cita. Renombrarlo es una
  decisión posterior, coordinada con ese informe.
- **ADR-046 §15. Resuelto en la revisión 3:** el propietario dispuso que los
  dobles de transporte son admisibles exclusivamente en `tests/` y nunca como
  adapters ficticios de producción (§3.1). ADR-046 no se modifica.
- **`SourcingRecord.market_evidence`.** Está tipado como
  `DeclaredDemandCapture` (ADR-052). Las observaciones de un conector futuro no
  tienen sitio ahí sin un ADR de transporte y persistencia.
