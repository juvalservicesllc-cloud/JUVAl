# Juval — Entorno de desarrollo y reproducibilidad

Este documento describe **qué herramientas hacen falta para construir y
verificar Juval**, y el estado verificado de cada nodo donde se trabaja.
No sustituye a `docs/architecture/TECHNOLOGY_DECISIONS.md`, que describe
las tecnologías del *producto*.

Última verificación: **2026-08-24**, ejecutando realmente las suites en
los tres nodos (no por inspección de documentación). E2E en Linux
re-verificado **2026-08-26** — ver §4 (el bloqueo de dependencias del
sistema para Chromium está resuelto, con evidencia medida).

## 1. Toolchain requerida

| Herramienta | Versión | Para qué | Pinned en |
|---|---|---|---|
| Python | 3.11+ (`pyproject.toml: requires-python`) | Backend, CLI, `pytest`, `tools/compliance_check.py` | `pyproject.toml` |
| Node.js | 24.x | Build y tests del frontend PWA (ADR-014) | `.node-version` (`24`) |
| npm | 11.x (viene con Node 24) | `npm ci` contra `frontend/package-lock.json` | lockfile |
| Chromium (Playwright) | el que fije `@playwright/test` | E2E reales contra el stack | `frontend/package-lock.json` |

**Node.js sí es una dependencia de build de Juval.** Una versión previa de
este documento afirmaba lo contrario ("ningún módulo de Juval requiere
Node"). Eso dejó de ser cierto cuando ADR-014 eligió la PWA como interfaz
principal: sin Node no hay frontend construible ni verificable. Sigue sin
ser una dependencia del *runtime* del backend, que es solo Python.

`psycopg` es el extra opcional `postgres` (ADR-017), **no** una dependencia
base: el store por defecto es SQLite (ADR-013). Importar
`supabase_execution_run_store` y construir el store funciona sin el driver;
solo abrir una conexión lo exige. CI instala únicamente `.[dev]` y por eso
esto se verifica en cada push.

## 2. Estado verificado por nodo (2026-08-24)

Los tres nodos están en el mismo commit y ejecutan la misma baseline.

| | Windows (workstation) | Linux (`juval-server`, 192.168.0.26) | GitHub Actions |
|---|---|---|---|
| SO | Windows 10 19045 | Ubuntu 24.04.4 LTS | ubuntu-latest |
| Python | 3.12.0 (`.venv`) | 3.12.3 (`.venv`) | 3.11 |
| Node / npm | 24.19.0 / 11.17.0 | 24.19.0 / 11.17.0 (vía nvm) | desde `.node-version` |
| Backend `pytest` | **352 passed, 7 skipped** | **352 passed, 7 skipped** | **352 passed, 2 skipped** |
| Frontend `npm test` | **112 passed** | **112 passed** | **112 passed** |
| `npm run build` (incluye `tsc -b`) | PASS | PASS | PASS |
| `npm run lint` (oxlint) | PASS | PASS | PASS |
| `tools/compliance_check.py` | 9 pass / 1 warn / 0 fail | 9 pass / 1 warn / 0 fail | 9 pass / 1 warn / 0 fail |
| E2E Playwright | **27/27 passing** | **27/27 passing** (§4, re-verificado 2026-08-26) | no se ejecuta (§4) |

La diferencia de `skipped` (7 vs 2) no es un fallo: con `psycopg` instalado
los tests que exigen una base real se saltan de uno en uno; sin el driver el
módulo entero se salta con `importorskip` y cuenta como un solo skip.

## 3. Node en shells no interactivos (Linux)

En `juval-server` Node está instalado con **nvm**, que se carga desde
`.bashrc` — y `.bashrc` no se ejecuta en una sesión SSH no interactiva. Por
eso `ssh juval@... 'node --version'` responde `command not found` aunque
Node exista. Cualquier automatización debe cargar nvm explícitamente:

```bash
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"
```

No es un fallo de instalación; es la diferencia entre shell interactivo y
no interactivo. Se documenta aquí porque es exactamente lo que rompe un
script de CI/cron que "funciona cuando lo pruebo a mano".

## 4. Blocker E2E en Linux — RESUELTO 2026-08-26

Histórico: el navegador de Playwright se instalaba sin sudo y funcionaba
para descargar el binario, pero Chromium no arrancaba porque faltaban
nueve librerías del sistema (`libasound.so.2`, `libatk-1.0.so.0`,
`libatk-bridge-2.0.so.0`, `libatspi.so.0`, `libgbm.so.1`,
`libXcomposite.so.1`, `libXdamage.so.1`, `libXfixes.so.3`,
`libXrandr.so.2`), que sí exigen `sudo`. El primer intento de resolverlo
falló porque `sudo` no resolvía el `npx` de nvm (`sudo: npx: command not
found` — nvm es user-scoped, `sudo` no hereda ese `PATH` por defecto).

**Resuelto 2026-08-26**: el usuario expuso el `PATH` de la instalación
nvm existente a `sudo` (sin instalar una segunda distribución de Node) y
ejecutó la instalación real de las dependencias. Evidencia medida por el
agente tras el hecho:

- `/var/log/apt/history.log` registra `Start-Date: 2026-08-26 13:12:37`,
  `Requested-By: juval (1000)`, instalando el set exacto de paquetes de
  Playwright (`libasound2t64`, `libatk-bridge2.0-0t64`, `libatk1.0-0t64`,
  `libatspi2.0-0t64`, `libgbm1`, `libxcomposite1`, `libxdamage1`,
  `libxfixes3`, `libxrandr2`, `xvfb`, fuentes, etc.).
- Las nueve librerías antes ausentes están confirmadas en disco
  (`find /usr/lib -iname <lib>` para cada una, todas bajo
  `/usr/lib/x86_64-linux-gnu/`).
- `ldd` sobre `chrome-headless-shell` y sobre `chrome`
  (`~/.cache/ms-playwright/chromium{,_headless_shell}-1234/...`) no
  reporta ninguna línea `not found`; ambos binarios responden a
  `--version` (`Google Chrome for Testing 151.0.7922.34`).
- **La suite E2E completa se ejecutó de verdad** en puertos aislados
  (backend `127.0.0.1:8001` con una base SQLite nueva; frontend
  `npm run build` + `npm run preview --host 127.0.0.1 --port 5180`, para
  no depender de los servidores de desarrollo ya corriendo en
  `0.0.0.0:5173`/`0.0.0.0:8000`) — **27/27 passing**, mismo conteo que el
  histórico de Windows.

La evidencia E2E real ahora existe en **ambos** nodos ejecutables
(Windows y Linux) — ver `frontend/e2e/README.md` para el detalle
completo del run 2026-08-26.

## 5. E2E: cómo se obtuvo la evidencia

27/27 contra el stack real (build de producción servido por
`npm run preview`, FastAPI real, SQLite real — sin mocks) en Windows y,
desde 2026-08-26, también en Linux (§4). Procedimiento completo y por qué
el puerto 5180 en `frontend/e2e/README.md`.

E2E **no** está en CI todavía: necesita los dos servidores levantados y las
dependencias de sistema del navegador. Se añadirá cuando sea reproducible;
mientras tanto es un gate manual, declarado como tal y no como automático.

## 6. Histórico

Este documento fue, hasta 2026-08-24, un diagnóstico de que Node.js no
estaba en el `PATH` de Git Bash en la workstation, lo que impedía los
lifecycle hooks de Ponytail (`ponytail-activate.js`, `ponytail-subagent.js`,
`ponytail-mode-tracker.js`). **Resuelto**: Node 24.19.0 está instalado y
resuelto en ambos shells de la workstation. Los skills manuales de Ponytail
nunca dependieron de esos hooks.

## 7. Relacionado

`CLAUDE.md` §5 (Ponytail), §17 (testing);
`docs/architecture/TECHNOLOGY_DECISIONS.md` (tecnologías del producto);
`docs/architecture/TESTING_STRATEGY.md`; `frontend/e2e/README.md`;
ADR-013 (SQLite), ADR-014 (PWA), ADR-017 (Supabase/`postgres` extra).
