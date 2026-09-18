"""One authorized real MFA cycle. Human-only viewer input; finite controller output.

START requires the human's blank dedicated-viewer confirmation. CLOSE, EOF, timeout,
signal or controller failure tears down owned resources. Never automates Admin.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time

from restricted_auth_display_lab import ROOT, admin, listeners, browser_pids, require, write_authority
from private_viewer_lab import viewer_commands, wait_for, stop_owned, require_listener_delta, VIEWER_PORTS

PATHS = {'READY': None, 'LOGIN': '/oauth2/authorize', 'ENROLLMENT': '/oauth2/two-factor-enable',
         'ENROLLMENT_COMPLETE': '/oauth2/two-factor-enable-complete', 'CONSENT': '/oauth2/consent',
         'MFA_CHALLENGE_CANDIDATE': '/oauth2/two-factor', 'MFA_METHOD_CANDIDATE': '/oauth2/two-factor-methods',
         'CALLBACK_REACHED': '/oauth/callback', 'CLOSED': None, 'FAILED': None, 'REJECTED': None,
         'UNEXPECTED_ROUTE': None, 'UNEXPECTED_TRANSITION': None, 'CALLBACK_REJECTED': None}
FAILURES = {'FAILED', 'UNEXPECTED_ROUTE', 'UNEXPECTED_TRANSITION', 'CALLBACK_REJECTED'}


def emit(value):
    print(json.dumps(value), flush=True)


def protocol(child, op=None):
    if op is not None:
        child.stdin.write(json.dumps({'op': op})+'\n')
        child.stdin.flush()
    require(select.select([child.stdout], [], [], 20)[0], 'CONTROLLER_TIMEOUT')
    line = child.stdout.readline(1024)
    require(len(line) < 1024, 'CONTROLLER_SCHEMA')
    value = json.loads(line)
    require(isinstance(value, dict) and set(value) == {'status', 'path'}, 'CONTROLLER_SCHEMA')
    require(value['status'] in PATHS and value['path'] == PATHS[value['status']], 'CONTROLLER_SCHEMA')
    return value


def main():
    require(len(sys.argv) == 2 and sys.argv[1] in {'1', '2'}, 'CYCLE')
    cycle = int(sys.argv[1])
    xsocket, xlock = Path('/tmp/.X11-unix/X100'), Path('/tmp/.X100-lock')
    require(not xsocket.exists() and not xlock.exists(), 'DISPLAY_BUSY')
    before_admin, before_ports = admin(), listeners()
    require(not browser_pids(), 'BROWSER_BUSY')
    require(not any(a.rsplit(':', 1)[-1] in {'18080', '5901', '6081', '9222'} for _, a in before_ports), 'PORT_BUSY')
    children, controller = [], None
    last, outcome = None, 'ABORTED'
    def interrupted(*_args):
        raise RuntimeError('INTERRUPTED')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    with tempfile.TemporaryDirectory(prefix=f'juval-real-mfa-{cycle}-') as directory:
        base = Path(directory)
        auth = base / 'Xauthority'
        write_authority(auth)
        empty = base / 'empty-authority'
        empty.touch(mode=0o600)
        runtime = base / 'runtime'
        runtime.mkdir(mode=0o700)
        env = {'PATH': os.environ['PATH'], 'HOME': str(runtime), 'TMPDIR': str(runtime),
               'DISPLAY': ':100', 'XAUTHORITY': str(auth)}
        try:
            xvfb = subprocess.Popen(['Xvfb', ':100', '-screen', '0', '1280x800x24',
                                     '-nolisten', 'tcp', '-auth', str(auth)], env=env,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            children.append(xvfb)
            wait_for(xsocket.exists, children)
            good = subprocess.run(['xdpyinfo', '-display', ':100'], env=env, capture_output=True, timeout=10)
            bad = subprocess.run(['xdpyinfo', '-display', ':100'], env={**env, 'XAUTHORITY': str(empty)}, capture_output=True, timeout=10)
            require(good.returncode == 0 and bad.returncode != 0, 'X11_AUTH')
            for command in viewer_commands(auth):
                children.append(subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            wait_for(lambda: listeners() == before_ports | VIEWER_PORTS, children)
            controller = subprocess.Popen(['node', 'tools/real_mfa_controller.mjs', str(cycle)], cwd=ROOT,
                env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
            require(protocol(controller) == {'status': 'READY', 'path': None}, 'CONTROLLER_START')
            require(admin() == before_admin, 'ADMIN_CHANGED')
            require_listener_delta(before_ports, VIEWER_PORTS)
            emit({'status': 'VIEWER_READY', 'cycle': cycle, 'display': ':100',
                  'human_confirmation_required_before_start': True})
            started = False
            deadline = time.monotonic()+1200
            while time.monotonic() < deadline:
                require(all(p.poll() is None for p in children) and controller.poll() is None, 'CHILD_EXITED')
                require(admin() == before_admin, 'ADMIN_CHANGED')
                require_listener_delta(before_ports, VIEWER_PORTS)
                op = None
                if select.select([sys.stdin], [], [], .5)[0]:
                    command = sys.stdin.readline(64)
                    if not command or command.strip() == 'CLOSE':
                        break
                    if command.strip() == 'START' and not started:
                        op, started = 'start', True
                if op is None and started:
                    op = 'observe'
                if op:
                    observed = protocol(controller, op)
                    if observed != last:
                        emit(observed)
                        last = observed
                    if observed['status'] == 'CALLBACK_REACHED':
                        outcome = 'CALLBACK_REACHED'
                        break  # Teardown is automatic, never preserve callback state.
                    if observed['status'] in FAILURES:
                        outcome = observed['status']
                        break
        except Exception:
            outcome = 'FAILED'
        finally:
            if controller is not None and controller.poll() is None:
                try:
                    require(protocol(controller, 'close')['status'] == 'CLOSED', 'BROWSER_CLOSE')
                    controller.stdin.close()
                    controller.wait(timeout=15)
                except Exception:
                    stop_owned(controller)
            for child in reversed(children):
                stop_owned(child)
        require(not browser_pids(), 'BROWSER_RESIDUAL')
        require(not xsocket.exists() and not xlock.exists(), 'DISPLAY_RESIDUAL')
        require(admin() == before_admin and listeners() == before_ports, 'BASELINE_CHANGED')
    require(not Path(directory).exists(), 'TEMP_RESIDUAL')
    emit({'status': outcome, 'cycle': cycle, 'browser_display_profile_runtime_removed': True,
          'listeners_restored': True, 'port_9222_absent': True, 'admin_metadata_unchanged': True})
    return 0 if outcome == 'CALLBACK_REACHED' else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        emit({'status': 'FAILED_OR_CLEANUP_UNVERIFIED'})
        raise SystemExit(1)
