# ADR-014: Elección de PWA como interfaz principal de Juval

- Estado: Aceptada — aprobada explícitamente por el usuario 2026-08-17
  ("PWA definitivamente"), reemplazando la incertidumbre PWA vs. `.exe`
  que ADR-005 dejaba abierta.
- Fecha: 2026-08-17

## Contexto

ADR-005 (`Estado: Aceptada`, 2026-08-16) hizo la arquitectura de Juval
**independiente** de la elección entre PWA y `.exe`: el Processing Core
y la Application Layer no saben ni les importa si quien los invoca es
un proceso CLI local, un backend detrás de una PWA, o un `.exe`
empaquetado. Esa independencia ya está demostrada en código, no solo en
diseño — `interfaces/cli/main.py` (implementado 2026-08-17) es un
cliente delgado real sobre `application.run_pipeline` +
`infrastructure/excel`, sin ninguna regla de negocio propia.

Con Fase 0-3 `COMPLETE` (185 tests pasando) y el CLI ya operativo como
primera interfaz de validación del Core, la pregunta que ADR-005
dejaba abierta — PWA, `.exe`, o ambos — seguía sin resolverse, y
bloqueaba explícitamente el inicio de Fase 4 (`PROJECT_PLAN.md` §Fase
4, `docs/PHASE_GATES.md` §Fase 4).

Se evaluaron ambas opciones en una sesión de análisis previa (comparación
objetiva contra ~25 dimensiones: arquitectura, UX, instalación,
actualizaciones, distribución, seguridad, auth, acceso remoto,
multiusuario, almacenamiento, integración con Supabase/Clerk, costes,
escalabilidad, dependencia de Windows/Internet, entre otras), sin que
esa sesión aprobara ninguna opción por sí misma. El usuario, con esa
comparación disponible, decidió explícitamente **PWA** como interfaz
principal de Juval, 2026-08-17.

## Decisión

Juval usará una **PWA (aplicación web progresiva)** como interfaz
principal de usuario. No se construirá un `.exe` como interfaz
principal. La arquitectura objetivo, conceptualmente:

```
PWA frontend
      │  HTTP/API
      ▼
interfaces/api/        (backend — cliente delgado)
      │
      ▼
application/            (casos de uso, ej. run_pipeline)
      │
      ▼
processing/              (Processing Core, sin I/O)
      │
      ▼
domain/                   (modelo de dominio puro)
```

con `infrastructure/` (Excel, persistencia, futuras integraciones)
proveyendo I/O por debajo, exactamente como ya lo hace hoy para el CLI
— no se introduce ninguna capa nueva de arquitectura, solo un segundo
cliente delgado (`interfaces/api/`) además del ya existente
(`interfaces/cli/`).

La PWA (frontend + `interfaces/api/`) es, como toda interfaz (ADR-001),
un **cliente delgado**: recibe input, lo traduce a una llamada de caso
de uso del Application Layer, y presenta el resultado. No debe
duplicar, en ningún punto:

- reglas de negocio ni cálculos financieros (`processing/profitability.py`,
  ADR-006);
- reglas de provenance ni estados de verificación (`domain/provenance.py`,
  ADR-003/ADR-004);
- scoring (`processing/decision_score.py`);
- validaciones de dominio (`processing/data_quality.py`,
  `__post_init__` de `domain/*.py`);
- lógica de importación/exportación de Excel (`infrastructure/excel/`,
  ADR-002).

Cualquier regla de negocio que aparezca en `interfaces/api/` o en el
frontend PWA durante la implementación futura es, por definición, un
defecto de arquitectura, no una decisión de esta fase.

## Consecuencias positivas

- Acceso desde cualquier navegador, sin instalación local.
- Independencia de Windows — el sistema deja de estar atado a un solo
  sistema operativo cliente.
- Actualizaciones centralizadas: un despliegue actualiza a todos los
  usuarios de inmediato, sin depender de que cada máquina instale una
  versión nueva manualmente.
- Camino natural hacia soporte multiusuario, cuando exista necesidad
  real demostrada (Fase 8/9).
- Posibilidad de acceso remoto nativa, sin trabajo adicional de
  VPN/RDP.
- Mejor compatibilidad con una futura autenticación (Clerk u otro
  proveedor, `PENDING`) — el modelo cliente-servidor ya asume una capa
  de auth como próximo paso natural, en vez de una adaptación forzada.
- Mejor compatibilidad con una futura persistencia compartida (Supabase
  u otra, `PENDING`) — la arquitectura cliente-servidor ya asume una
  base de datos remota como evolución natural del `ExecutionRunStore`
  (`Protocol`, ADR-013) ya existente.

## Consecuencias negativas / costes

- Requiere construir un backend HTTP nuevo (`interfaces/api/`) que hoy
  no existe — a diferencia del CLI, que ya reutiliza directamente
  `application.run_pipeline`.
- Requiere un frontend separado, con su propio ciclo de build/deploy.
- El manejo de archivos Excel deja de ser un `Path` de filesystem local
  directo (como en el CLI) y pasa a requerir upload/download vía HTTP —
  trabajo real de diseño, no solo "conectar un botón".
- Activa, en un plazo razonable, la necesidad de autenticación (Clerk u
  otro) para no exponer el sistema sin control de acceso — aunque esa
  decisión sigue sin tomarse en este ADR.
- Exige diseñar correctamente la ejecución de tareas largas (el
  pipeline puede tardar más que un timeout de request HTTP razonable)
  — mecanismo concreto (jobs asíncronos, polling, websockets) sin
  definir todavía.
- Mayor superficie de seguridad que un proceso local (HTTP expuesto,
  necesidad de HTTPS, CORS, rate limiting) frente al CLI o un `.exe`.
- Requiere una decisión de deployment/hosting que hoy no existe
  (ninguna decisión de infraestructura cloud está tomada).
- Mayor complejidad de implementación que el estado actual (CLI local)
  — se acepta deliberadamente a cambio de las consecuencias positivas
  de arriba.

## Límites explícitos de esta decisión

**Esta decisión NO aprueba, ni implícita ni automáticamente, ninguna de
las siguientes tecnologías o decisiones**. Cada una requiere su propio
análisis y aprobación explícita cuando corresponda, siguiendo el mismo
proceso que este ADR (`docs/DEVELOPMENT_LOOP.md`):

- Framework de backend concreto (FastAPI u otro) — mencionado como
  candidato en `ARCHITECTURE.md` §15, nunca aprobado por ADR.
- Framework de frontend concreto (Next.js, React, u otro).
- Tailwind CSS ni ningún sistema de estilos concreto.
- Vercel ni ningún proveedor de hosting/deployment.
- Supabase (persistencia compartida/remota, Fase 8) — sigue `PENDING`
  explícito (`CLAUDE.md` §14), sin necesidad real demostrada todavía.
- Clerk (autenticación, Fase 9) — sigue `PENDING` explícito.
- Docker ni ninguna estrategia de contenedores/CI-CD.
- Ningún proveedor cloud concreto.

`PWA = Next.js`, `PWA = Vercel`, `PWA = Supabase`, `PWA = Clerk`,
`PWA = FastAPI` son todas asunciones inválidas a partir de este ADR. La
única decisión tomada aquí es "PWA como interfaz principal" — nada más.

## Relación con ADR-005

ADR-005 estableció la **independencia arquitectónica** de esta
elección: diseñó el sistema para que PWA, `.exe`, o ambos pudieran
implementarse sin tocar `domain/`, `processing/`, `application/`, ni
`infrastructure/`. Esa decisión de diseño **no se modifica ni se
revierte** por este ADR — sigue siendo la razón por la que elegir PWA
ahora no obliga a rediseñar nada del Core ya implementado y probado
(185 tests). ADR-014 es la continuación directa de ADR-005: donde
ADR-005 dejó la elección abierta deliberadamente, ADR-014 la cierra con
la decisión real del usuario. Ambos ADRs coexisten sin contradicción;
ADR-005 no se marca como superseded, porque su contenido (la
independencia de diseño) sigue siendo exactamente cierto.

## Impacto sobre `.exe`

`.exe` (Windows, vía PyInstaller u otro) deja de ser una opción
candidata para la interfaz **principal** de Juval. No se descarta como
imposible para siempre (la independencia de ADR-005 lo seguiría
permitiendo técnicamente si en el futuro apareciera una necesidad
distinta y concreta), pero no es el camino que se construirá — esta
decisión no necesita revisarse para eso, simplemente no hay trabajo
planeado en esa dirección.

## Consecuencias sobre el plan de fases

Fase 4 (`PROJECT_PLAN.md`) queda orientada concretamente a "Dashboard
PWA" — `interfaces/api/` (backend) + un frontend PWA, en vez de la
ambigüedad previa "Dashboard / PWA [pendiente de resolver con `.exe`]".
Fase 4 sigue `BLOCKED` hasta que se resuelvan las decisiones técnicas
que este ADR deja explícitamente pendientes (framework backend,
framework frontend, deployment) — este ADR resuelve el bloqueo de
*elección de interfaz*, no el resto de las decisiones bloqueantes de
Fase 4. Ningún código de Fase 4 se implementó como parte de este ADR.

## Reversibilidad

Media. Revertir "PWA" por "`.exe`" después de haber construido
`interfaces/api/` + frontend implicaría descartar ese trabajo específico
de interfaz — pero, exactamente por diseño de ADR-005, no implicaría
tocar `domain/`, `processing/`, `application/`, ni `infrastructure/`.
El costo de una reversión futura está acotado a la capa de interfaz,
nunca al Core.

## Relacionado

`docs/adr/ADR-005-independencia-pwa-exe.md` (diseño de independencia,
no modificado por este ADR), `docs/architecture/ARCHITECTURE.md` §10
(análisis comparativo original), `docs/PROJECT_PLAN.md` Fase 4
(alcance actualizado en el mismo cambio que este ADR),
`docs/PROJECT_STATUS.md` (estado actualizado en el mismo cambio),
`docs/architecture/TECHNOLOGY_DECISIONS.md` (matriz de tecnologías,
filas PWA/`.exe` actualizadas en el mismo cambio).
