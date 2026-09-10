# ADR-033 — Estrategia de verificación de identidad sin credenciales administrativas

**Estado: Propuesta (PROPOSED)** — pendiente de decisión explícita del
usuario. No implementa nada, no cambia ninguna configuración, no revoca
ninguna credencial y no altera ningún gate de cumplimiento.
**Fecha: 2026-09-09.**
**Relacionada con:** ADR-032 (credenciales de FusionAuth con alcance por ciclo
de vida), ADR-031 (alojamiento self-hosted), ADR-028 (FusionAuth como
proveedor), ADR-021 (requisitos HARD del IdP),
`docs/compliance/SP_API_REGISTRATION_REMEDIATION.md` §38.5/§41–§52,
`docs/research/IDENTITY_AMAZON_DEEP_RESEARCH.md` (investigación que respalda
esta propuesta), `tools/verify_identity_behavior.py`.

## Contexto

La verificación behavioral de RF-03 (contraseña, lockout, MFA) y de Control 6
está bloqueada desde §41 (2026-09-01) por una sola razón: la herramienta
diseñada para producirla, `tools/verify_identity_behavior.py`, depende de una
API key administrativa de FusionAuth, y ninguna de las credenciales emitidas
para ese propósito autentica.

§52 (2026-09-08) cerró la forense estática con dos resultados de igual peso:
la pregunta arquitectónica quedó contestada (`DistributedCacheNotifier` es
asíncrono, `VERIFIED_IMPLEMENTATION`) y **no** se produjo una causa raíz
(`ROOT_CAUSE = NOT_PROVEN`). §52.7 anticipó, como plan y no como evidencia,
rediseñar la verificación alrededor de flujos públicos/de usuario.

La investigación de 2026-09-09 añade tres hechos externos que convierten ese
plan en una decisión defendible en lugar de una preferencia:

1. FusionAuth **documenta** que una key recién creada puede tardar en ser
   utilizable, *"hasta 60 segundos"* si falla la comunicación entre nodos
   (`VERIFIED_OFFICIAL_DOC`). El mecanismo que §52.2 dedujo del bytecode es
   comportamiento documentado por el fabricante, no un defecto. Sigue sin
   explicar IV3, que falló **después** de un reinicio que sí repobló la caché.
2. FusionAuth documenta que **`401` cubre tanto credencial inválida como
   permiso insuficiente** (*"All secured APIs will return an `401
   Unauthorized` response if improper credentials are provided"*), y la issue
   abierta #46 lo confirma como deuda de diseño del propio producto. La
   imposibilidad de discriminar que §43 reportó **no era una carencia de
   método de JUVAl**: es una propiedad del proveedor. Ninguna sonda de caja
   negra adicional aporta un bit nuevo.
3. El endurecimiento 1.65/1.66 (keys tenant-scoped rechazadas en endpoints de
   alcance global) **no aplica** a ninguno de los endpoints que las
   herramientas usan: todos figuran en la referencia oficial como *"API Key
   Authentication — a tenant-scoped or global API key may be used"*. Línea
   cerrada.

Al mismo tiempo, el runtime de producción **no usa ninguna API key de
FusionAuth** (`src/juval/interfaces/api/auth.py::build_verifier` consume solo
el JWKS público, anónimo — `VERIFIED_SOURCE_CODE`). La anomalía vive
íntegramente en el plano administrativo, que es exactamente la separación que
ADR-032 fijó.

Es decir: se está gastando esfuerzo en reparar una dependencia que la
arquitectura objetivo no necesita, para producir una evidencia que puede
obtenerse por otra vía.

## Decisión propuesta

**La verificación de comportamiento de identidad (RF-03, Control 6, lockout,
MFA) deja de depender de credenciales administrativas de FusionAuth.**

Concretamente:

1. **Vía primaria — flujos de usuario, cero API keys.** El operador crea un
   usuario desechable y enrola TOTP **en la consola administrativa de
   FusionAuth** (acción humana, sin credencial programática). El agente
   observa después únicamente superficies públicas: las páginas hosted de
   login, el desafío de segundo factor, el rechazo de contraseñas contra la
   política del tenant, y el bloqueo tras N intentos. Se registran estados
   HTTP, códigos de error y orden de pasos — **nunca** contraseñas, secretos
   TOTP, códigos, cookies ni JWT.

2. **`tools/verify_identity_behavior.py` sale del camino crítico.** No se
   borra ni se declara inválido: su matriz de casos y su lógica de
   clasificación (`401/403 -> BLOCKED, nunca PASS`, ADR-032) siguen siendo
   correctas y reutilizables. Deja de ser la única vía de evidencia, y por
   tanto deja de ser un bloqueador.

3. **Se añade un sexto bucket al ciclo de vida de ADR-032: "ninguna
   credencial".** ADR-032 enumera bootstrap, verificación y runtime. La
   verificación behavioral pasa a esta categoría nueva. Es una extensión de
   ADR-032, no una enmienda: ninguna regla operativa suya se modifica.

4. **La reproducción de comportamiento no resuelto ocurre en un laboratorio
   aislado, nunca en el tenant de producción.** La frontera mínima suficiente
   es una **instancia FusionAuth desechable separada** — no un tenant
   separado: las preguntas abiertas (orden hosted de `passwordChangeRequired`
   vs MFA, equivalencia de validación entre rutas de cambio de contraseña,
   comportamiento de `loginPolicy=Required` sin método enrolado) son
   propiedades de instancia, y un tenant no las aísla. Especificación completa
   en `docs/research/IDENTITY_AMAZON_DEEP_RESEARCH.md` §14.

5. **La investigación de la anomalía de API key queda cerrada.**
   `API_AUTH = FAIL` y `ROOT_CAUSE = NOT_PROVEN` se conservan como estado
   permanente, no como trabajo pendiente. Reabrirla exige un **fallo concreto
   nuevo**, no curiosidad. La lista de lo que no se vuelve a probar está en
   §15 de la investigación y se considera parte de esta decisión.

## Lo que esta decisión NO hace

- No revoca ninguna credencial existente (eso es acción manual del operador,
  ADR-032).
- No promueve ningún control a `VERIFIED`. `RF-03`, `RF-04` siguen
  `NOT_VERIFIED`; `CONTROL_6` sigue `B — PARTIALLY_SATISFIED`;
  `REAPPLICATION GATE` sigue `BLOCKED`.
- No decide la topología de autenticación del navegador (BFF vs cliente
  público SPA con PKCE). Esa es una decisión **PENDING** del usuario y le
  corresponde un ADR propio (ADR-034 propuesto).
- No decide el mecanismo de Control 6. También es decisión del usuario, con
  ADR propio (ADR-035 propuesto); la investigación recomienda la Opción C
  (pre-validación del lado de JUVAl en la ruta de aprovisionamiento).
- No autoriza ejecutar ningún login, crear ningún usuario ni tocar el frontend.

## Consecuencias

**A favor.** El bloqueo de RF-03 deja de depender de un fallo cuya causa es
indemostrable. La evidencia pasa a producirse sobre las rutas que Amazon
realmente audita — las que un usuario humano recorre — en lugar de sobre una
API administrativa que el producto no usa. La superficie de credenciales de la
verificación baja a cero, que es estrictamente mejor que "mínimo privilegio".

**En contra.** La vía primaria requiere participación del operador (crear el
usuario y enrolar TOTP en consola), así que es menos automatizable que una
herramienta con API key. Es un coste real y se acepta a cambio de eliminar una
dependencia rota y una superficie de credencial completa.

**Riesgo aceptado y declarado.** Sin API key, el agente no puede desactivar ni
borrar el usuario desechable. Queda como cuenta claramente etiquetada,
inutilizable en la práctica (su contraseña no se conserva en ningún sitio) y
visible para el operador — el mismo trade-off que ADR-032 ya documentó, ahora
sin la credencial.

## Estado

**Propuesta.** Requiere confirmación explícita del usuario antes de que
cualquier parte se ejecute. Mientras siga en `Propuesta`, ni el laboratorio ni
la verificación por flujos de usuario se ponen en marcha.
