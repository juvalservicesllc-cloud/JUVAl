# ADR-055 — Selección del modo de autenticación fail-closed

- Estado: **Aceptada** (2026-11-04). Las decisiones 1–10 fueron aprobadas
  explícitamente por el propietario en la instrucción SEC-01C. La
  implementación local está **pendiente de revisión y commit**; no se ha
  desplegado.
- Origen: SEC-01A (backend Railway documentado inactivo, «Application not
  found») y SEC-01B (diseño).
- Relacionado: ADR-028/031 (FusionAuth), ADR-034 (BFF), ADR-036 (sesiones
  duraderas, despliegue sólo-bearer), ADR-038 (topología app/api/id),
  ADR-018 (Railway). No cambia el RBAC (`ROLE_PERMISSIONS`), el pin RS256 ni
  ninguno de esos ADR.

## Contexto

Hasta este ADR, `auth.py::auth_mode()` devolvía `disabled` cuando faltaba
`JUVAL_AUTH_MODE`, y `current_principal()` entregaba un principal anónimo con
**todos** los permisos siempre que no hubiera verificador. Por tanto:

1. Un despliegue sin la variable quedaba abierto. El de Railway de 2026-08-18
   se hizo así (`ACCESS_CONTROL.md`); SEC-01A lo encontró inactivo.
2. El acceso anónimo dependía de que `verifier is None`, no del modo:
   `set_verifier(None)` dejaba la API anónima aunque el modo fuera `oidc`.
3. El verificador se construía en la primera petición: un `oidc` sin issuer o
   audience arrancaba y fallaba después.
4. El modo y el claim de roles se volvían a leer del entorno durante la
   ejecución.
5. `/docs`, `/redoc` y `/openapi.json` eran públicos en cualquier modo.

## Decisión

1. **Modo obligatorio.** `JUVAL_AUTH_MODE` ∈ {`oidc`, `disabled`}, sin valor
   por defecto. Ausente, vacío o desconocido detiene el arranque. El mensaje
   nombra la variable y nunca repite su valor.
2. **`disabled` es un laboratorio local confirmado.** Exige además
   `JUVAL_AUTH_DISABLED_CONFIRM=yes-loopback-lab-only` (mismo patrón que
   `JUVAL_SESSION_STORE_MEMORY_CONFIRM`, ADR-036).
3. **`disabled` se niega en entornos de despliegue.** No arranca si existe
   alguna variable `RAILWAY_*` o `VERCEL*`, ni si `JUVAL_CORS_ORIGINS` lista un
   origen que no sea loopback.
4. **Control por petición, no solo por variables.** En `disabled`, cada
   petición protegida exige:
   - cliente y dirección local del socket loopback (`scope["client"]` y
     `scope["server"]`, que uvicorn toma del socket);
   - ninguna cabecera de proxy o túnel (`Forwarded`, `Via`, `X-Forwarded-*`,
     `X-Real-IP`, `CF-Connecting-IP`, `CF-Ray`, `True-Client-IP`);
   - `Host` loopback (bloquea túneles que conservan el host público y el DNS
     rebinding);
   - `Origin`, si existe, loopback (una web pública no puede usar el navegador
     del operador contra el laboratorio).

   Si algo falla: 403 sin datos.
5. **Estado inmutable por instancia.** El lifespan resuelve `AuthSettings`
   (dataclass congelada) y la instala en `app.state` de la instancia que
   arranca (el argumento del lifespan, nunca el `app` global del módulo: otra
   instancia que comparta el lifespan no puede escribir ni borrar la
   configuración de una que ya está en marcha). Otra instalación sobre
   una instancia en marcha falla; el apagado la retira. Ninguna decisión de
   permisos vuelve a leer el entorno: ni el modo, ni el claim de roles (la BFF
   usa `verifier.roles_claim`).
6. **La autorización depende del modo, nunca del verificador.**
   - `AuthSettings(oidc)` sin verificador no se puede construir.
   - `set_verifier(None)` significa «construirlo desde el entorno», no
     «anónimo».
   - Una instancia que no arrancó responde 503 a toda ruta protegida.
   - En `oidc`, cualquier fallo del verificador (JWKS caído, token inválido)
     es 401, y un fallo del resolvedor de sesión es 500. Nunca acceso.
7. **OIDC se valida al arrancar.** El verificador se construye en el lifespan:
   issuer o audience ausentes detienen el arranque. El JWKS se sigue
   descargando en la primera verificación, sin red al arrancar.
8. **Documentación de la API solo en el laboratorio.** Un middleware responde
   404 a `/docs`, `/redoc`, `/openapi.json` y el redirect OAuth2 de Swagger,
   salvo en `disabled` con una petición de laboratorio válida. En `oidc`
   siempre 404; no hay opt-in, porque no existe una necesidad demostrada.
9. RBAC sin cambios.

## Garantías y límites

- No hay camino de código en `oidc` que devuelva el principal de laboratorio.
- **Límite conocido:** un proceso en la misma máquina que reenvíe tráfico
  externo a `127.0.0.1`, reescriba `Host` a loopback y elimine todas las
  cabeceras de reenvío es indistinguible de un cliente local. Ningún control
  dentro del proceso lo puede detectar. Queda **prohibido por política**:
  nunca publicar con un proxy, túnel o reenvío de puertos una API en modo
  `disabled`. El túnel SSH del propietario hacia su propio equipo es el uso
  previsto (`FRONTEND_NEXT_OWNER_ACCEPTANCE.md` §1).
- Detectar 127.0.0.1 no es una garantía de privacidad. La protección real
  para cualquier despliegue es `oidc`.
- La lista de plataformas (Railway, Vercel) es una capa entre varias. Otra
  plataforma sigue frenada por el control por petición.

## Consecuencias

- Todo entorno debe declarar el modo. El laboratorio E2E
  (`frontend-next/playwright.config.ts`) y los comandos del propietario
  añaden la confirmación.
- Ya no es posible un rollback a `disabled` en Railway
  (`deploy/fusionauth/README.md` actualizado): el rollback es dejar el backend
  sin conexión.
- Las pruebas que usan el laboratorio lo piden de forma explícita (fixture
  `auth_lab`, `tests/integration/conftest.py`); no hay activación global.
- Esto no completa RF-03/RF-04 ante Amazon: la identidad sigue PARTIAL y la
  producción no está activada.

## Pruebas

- `tests/integration/test_auth_mode_fail_closed.py`: modo ausente, vacío o
  desconocido; laboratorio sin confirmación, en plataforma o con CORS
  público; cliente remoto en las 14 rutas de datos (tomadas de la propia
  app); dirección local no loopback; cada cabecera de reenvío; `Host` y
  `Origin` no loopback; IPv6 y IPv4 mapeada; OIDC incompleto; sin token en
  las 14 rutas; token inválido; verificador ausente y JWKS caído;
  resolvedor de sesión roto; inmutabilidad ante cambios de entorno; dos
  instancias simultáneas con modos distintos sin contaminación;
  docs; ausencia de valores en errores y logs.
- Se mantienen las negativas de `test_api_auth.py`, `test_auth_hardening.py`
  y `test_api_bff.py`.

## Alternativas descartadas

- **Cambiar el valor por defecto a `oidc`:** rompe todo hasta que exista un
  IdP y no corrige la dependencia del verificador.
- **Solo comprobar loopback:** no detecta proxies locales.
- **Solo detectar plataformas por variables:** lista incompleta.
- **Opt-in para docs en `oidc`:** sin necesidad demostrada.
