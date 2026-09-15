# Private human viewer lab — 2026-09-15

Status: SYNTHETIC PRIVATE VIEWER GATE PASS. Not authorization for real MFA.
Baseline: e3d276652e2fd9461f599f964f9e0aa04b9f80bf (local only).

## Implementation and boundary

`tools/private_viewer_lab.py` owns a temporary synthetic server, Xvfb :100,
x11vnc and websockify, and the existing restricted evidence controller. The
Xauthority helper is shared with the earlier display lab. No stock MCP changes,
new package, persistent service or host security change was needed.

Xvfb requires fresh private Xauthority and disables TCP. The harness refuses a
busy :100, existing dedicated browser or occupied viewer/CDP ports. VNC listens
only at 127.0.0.1:5901, IPv6 disabled; noVNC/websockify only at 127.0.0.1:6081.
Selection/clipboard transfer and x11vnc remote commands are disabled by explicit
flags, verified in process metadata. Clipboard contents were never inspected;
clipboard suppression was not tested by transferring data.

The page contains only `JUVAl PRIVATE VIEWER SYNTHETIC TEST` and a confirmation
button. The harness checks a VNC protocol banner and serves noVNC static content;
it never reads framebuffer images or sends viewer input. Human confirmation is
required separately from the page's boolean interaction event. Neither is a
cryptographic identity attestation: another same-host client could forge input.

## Measured runtime evidence

- Authorized X11 connection accepted; empty authority rejected.
- Restricted controller reached the synthetic /login page; fixture served.
- Actual viewer processes had the dedicated display and required flags.
- Only the expected loopback fixture/VNC/websockify listeners were added;
  no X11 TCP, public/LAN viewer listener or port 9222.
- Human explicitly confirmed visual access and interaction. The synthetic
  page's independent interaction event was true before shutdown.
- Harness completed with status CONFIRMED, exit 0. Browser, viewers, Xvfb,
  socket/lock and private temporary directory were cleaned up. Listener baseline
  restored; repository state unchanged by runtime.
- Independent post-close check: no dedicated browser, :100 socket/lock or
  viewer/CDP ports. Admin PID 396207 retained executable/start-time metadata.
  No authenticated Admin state was read.

## Reproduce only with synthetic authorization

```sh
.venv/bin/python tools/private_viewer_lab.py
```

After WAITING_FOR_HUMAN, the Windows operator opens:

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:6081:127.0.0.1:6081 juval@192.168.0.26
```

Then visit `http://127.0.0.1:6081/vnc.html?autoconnect=1&resize=scale` and press
**Confirm synthetic interaction**. Once the operator attests the button changed
to **SYNTHETIC INTERACTION CONFIRMED**, send `CONFIRMED` to harness stdin. `STOP`,
stdin closure or its 20-minute deadline also initiates cleanup, without claiming
human confirmation. Normal confirmed cleanup was tested; deadline/crash paths
are implemented but not claimed behaviorally verified.

## Limits and next gate

No VNC password is created: loopback plus an SSH tunnel is accepted only for this
non-sensitive disposable lab. Any local host process/user able to connect to the
loopback port can access VNC; local Windows processes can access the forwarded
port. This is not an authenticated user-isolation boundary. Separate X11 displays
also do not defend against a malicious process running as the same Unix user.
No viewer recording, screenshots, browser traces or secret-persistence experiment
was performed. Whole-tree Chromium sandbox remains PARTIAL. Stock MCP remains
uncleared for sensitive authentication.

Next: explicit review of the real-flow route/callback boundary, private viewer
residual risk, independent Marcus readback and mandatory cleanup protocol. No
FusionAuth, Marcus, password/TOTP, OAuth or production interaction occurred.
ADR-042 and ADR-041 remain Proposed; RF-03 remains Partial; MFA remains unauthorized.

## Validation

46 focused pytest tests passed (including the restricted-controller Node wrapper).
Offline compliance: 7 PASS, 1 existing incident-plan placeholder WARN, no FAIL.
Working-tree pattern secret scan passed; this is not absolute absence of secrets.
Diff whitespace check passed; frozen frontend trees unchanged. No dependency
changes, network audits or Git publication attempts were required in this phase.
