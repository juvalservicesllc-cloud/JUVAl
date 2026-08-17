# Juval — Development Environment (Nota de infraestructura)

Este documento **no** describe el runtime de Juval (Python 3.11+,
`openpyxl`, `pytest` — ver `docs/architecture/TECHNOLOGY_DECISIONS.md`).
Describe el entorno de desarrollo del agente (Claude Code) usado para
trabajar en este repositorio, y un hallazgo de diagnóstico sobre ese
entorno que no está resuelto. No se modificó ningún archivo del proyecto
Juval (`src/`, `tests/`, `pyproject.toml`, `docs/architecture/*`) al
producir este documento.

Última verificación: 2026-08-16, por inspección directa del entorno
(`which node`, `which npm`, `$PATH`, y el contenido de
`~/.claude/plugins/cache/ponytail/ponytail/4.9.0/hooks/`).

## 1. Hallazgo

Claude Code, en este entorno, usa el plugin **Ponytail** (`ponytail@ponytail`,
versión `4.9.0` instalada en `~/.claude/plugins/cache/ponytail/ponytail/4.9.0/`)
para el modo de simplicidad/anti-sobreingeniería activo en este proyecto
(`CLAUDE.md` §5, modo FULL por defecto).

Ponytail integra con Claude Code mediante **lifecycle hooks** — scripts
que el propio Claude Code invoca automáticamente en ciertos eventos
(activación de modo, tracking de subagentes, etc.), definidos en
`~/.claude/plugins/cache/ponytail/ponytail/4.9.0/hooks/claude-codex-hooks.json`:

```
node "${CLAUDE_PLUGIN_ROOT}/hooks/ponytail-activate.js"
node "${CLAUDE_PLUGIN_ROOT}/hooks/ponytail-subagent.js"
node "${CLAUDE_PLUGIN_ROOT}/hooks/ponytail-mode-tracker.js"
```

Estos tres hooks **requieren Node.js** en el `PATH` del shell no
interactivo que Claude Code usa para ejecutarlos.

**Node.js y npm no están disponibles** en el entorno Git Bash que Claude
Code usa en esta máquina:

```
$ which node
which: no node in (...$PATH completo, sin ninguna entrada de Node...)
$ node --version
/usr/bin/bash: line 3: node: command not found
$ which npm
which: no npm in (...mismo $PATH...)
```

El `$PATH` de este shell (Git Bash / MinGW64) no contiene ningún
directorio de instalación de Node.js — no es un problema de una variable
mal configurada, es que Node no está instalado, o está instalado pero
fuera de este `PATH` específico.

## 2. Consecuencia real

Con Node ausente del `PATH`, los tres lifecycle hooks de Ponytail no
pueden ejecutarse cuando Claude Code intenta invocarlos. Consecuencias
concretas:

- **La activación automática de modo Ponytail no funciona.** El hook
  `ponytail-activate.js`, que normalmente activaría el modo FULL sin
  intervención del usuario en cada prompt, no se ejecuta.
- **El tracking automático de subagentes no funciona.** `ponytail-subagent.js`
  y `ponytail-mode-tracker.js` tampoco se ejecutan.
- **Los skills manuales de Ponytail siguen disponibles y funcionan.**
  `/ponytail-review`, `/ponytail-audit`, `/ponytail-debt`,
  `/ponytail-gain`, `/ponytail-help` y el modo invocado explícitamente
  (`ponytail:ponytail`) no dependen de estos lifecycle hooks — son
  skills invocados directamente por el agente o por el usuario, no
  disparados por el evento automático que Node ejecutaría. Esta
  distinción es la documentada en el propio README de Ponytail
  (`README.es.md:112`): *"si [node] no está [en el PATH], los skills
  igualmente funcionan, la activación automática simplemente queda en
  silencio en vez de lanzar un error en cada prompt"*.
- **No hay ningún error visible.** El fallo es silencioso por diseño del
  propio plugin — no hay una alerta que indique que la activación
  automática dejó de funcionar; solo se detecta por inspección directa
  del entorno, como se hizo aquí.

## 3. Qué NO es este hallazgo

- **No es una dependencia del runtime de Juval.** Ningún módulo de
  `src/juval/` importa ni requiere Node.js, JavaScript, ni npm — el
  stack de Juval es Python 3.11+ (`openpyxl`, `pytest`), documentado en
  `docs/architecture/TECHNOLOGY_DECISIONS.md`. Los 177 tests del
  proyecto (`docs/architecture/TESTING_STRATEGY.md`) no se ven afectados
  por esto en absoluto.
- **No es un problema de configuración de Juval** — es un problema del
  entorno de desarrollo del agente (Claude Code + plugin Ponytail en
  esta máquina), independiente de este repositorio.
- **No está resuelto.** Ver §5.

## 4. Clasificación

Node.js debe tratarse como una **dependencia del entorno de desarrollo**
(la herramienta que opera sobre este repositorio), nunca como una
dependencia del proyecto Juval en sí. Esta distinción importa para no
mezclar accidentalmente "Node.js" en `pyproject.toml`,
`docs/architecture/TECHNOLOGY_DECISIONS.md` (matriz de tecnologías del
*producto*), ni en ningún ADR de Juval — no aplica ahí.

## 5. Estado

**NOT RESOLVED.** Este documento es un diagnóstico, no una corrección.
No se instaló Node.js ni se modificó ningún hook, `PATH`, ni archivo de
configuración de Claude Code o de Ponytail como parte de esta tarea.

## 6. Solución prevista (no ejecutada)

1. Instalar Node.js LTS en la máquina.
2. Verificar disponibilidad de `node`/`npm` en **ambos** shells que este
   entorno usa — no alcanza con verificar uno solo, porque cada shell
   resuelve su propio `PATH` de forma independiente:
   - PowerShell: `Get-Command node`, `node --version`.
   - Git Bash: `which node`, `node --version`.
3. Volver a verificar que los lifecycle hooks de Ponytail se ejecutan
   (activación automática de modo sin intervención manual) tras
   confirmar que ambos shells resuelven `node`.

Ninguno de estos pasos se ejecutó en esta tarea.

## 7. Relacionado

`CLAUDE.md` §5 (Ponytail, modo FULL), `docs/architecture/TECHNOLOGY_DECISIONS.md`
(matriz de tecnologías del *producto* Juval — Node.js no aparece ahí
porque no es una dependencia del producto).
