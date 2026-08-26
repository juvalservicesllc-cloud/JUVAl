# `juval-host-monitor` systemd user units

Mirrors of the unit files running live on `juval-server` at
`~/.config/systemd/user/juval-host-monitor.{timer,service}` (H-15, ADR-027,
Gate 6). Kept here so the monitoring setup is reproducible from Git instead
of existing only as host-local state — see
`docs/compliance/HOST_CONTROLS_JUVAL_SERVER.md` §4.

## Install (no sudo — user-scoped systemd instance)

```bash
mkdir -p ~/.config/systemd/user
cp tools/systemd/juval-host-monitor.timer ~/.config/systemd/user/
cp tools/systemd/juval-host-monitor.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now juval-host-monitor.timer
loginctl enable-linger "$USER"   # survive reboot without an interactive login (H-16)
```

## Verify

```bash
systemctl --user list-timers juval-host-monitor.timer
journalctl --user -u juval-host-monitor.service -n 20
```

If either file here is edited, copy the updated version back into
`~/.config/systemd/user/` and re-run `daemon-reload` — the live host does
not read from this path automatically.
