"""Disposable synthetic-only X11 lab. No viewer, real login, sudo or host config.

Creates private Xauthority material without printing it. Never reads Admin state.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import secrets
import signal
import struct
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
BROWSER = '/opt/juval-browser/chromium-1243/'


def admin():
    p = Path('/proc/396207')
    return (str((p / 'exe').resolve()), (p / 'stat').read_text().rsplit(')', 1)[1].split()[19])


def listeners():
    text = subprocess.run(['ss', '-H', '-lntu'], capture_output=True, text=True, check=True).stdout
    return {(s[0], s[4]) for line in text.splitlines() if len(s := line.split()) >= 5}


def browser_pids():
    result = set()
    for p in Path('/proc').iterdir():
        if p.name.isdigit():
            try:
                if str((p / 'exe').resolve()).startswith(BROWSER):
                    result.add(int(p.name))
            except OSError:
                pass
    return result


def require(value, code):
    if not value:
        raise RuntimeError(code)


def main():
    display = ':100'
    socket = Path('/tmp/.X11-unix/X100')
    lock = Path('/tmp/.X100-lock')
    require(not socket.exists() and not lock.exists(), 'DISPLAY_BUSY')
    before_admin, before_ports, before_browser = admin(), listeners(), browser_pids()
    before_git = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=ROOT, capture_output=True, check=True).stdout
    require(not before_browser, 'DEDICATED_BROWSER_BUSY')
    xvfb = None
    result = {}
    with tempfile.TemporaryDirectory(prefix='juval-auth-display-') as directory:
        base = Path(directory)
        auth = base / 'Xauthority'
        # Xauthority binary record: wildcard family, empty address, display 100.
        # Only the fresh test X server receives this credential; no Admin auth is read.
        def field(value):
            return struct.pack('!H', len(value)) + value
        payload = struct.pack('!H', 65535) + field(b'') + field(b'100') + field(b'MIT-MAGIC-COOKIE-1') + field(secrets.token_bytes(16))
        fd = os.open(auth, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
        del payload
        empty = base / 'no-authority'
        empty.touch(mode=0o600)
        runtime = base / 'runtime'
        runtime.mkdir(mode=0o700)
        env = {'PATH': os.environ['PATH'], 'HOME': str(runtime), 'DISPLAY': display,
               'XAUTHORITY': str(auth), 'JUVAL_LAB_TMP': str(runtime)}
        try:
            xvfb = subprocess.Popen(['Xvfb', display, '-screen', '0', '1280x800x24',
                                     '-nolisten', 'tcp', '-auth', str(auth)],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(100):
                if socket.exists() or xvfb.poll() is not None:
                    break
                time.sleep(.05)
            require(xvfb.poll() is None and socket.exists(), 'DISPLAY_START_FAILED')
            good = subprocess.run(['xdpyinfo', '-display', display], env=env, capture_output=True, timeout=10)
            bad = subprocess.run(['xdpyinfo', '-display', display], env={**env, 'XAUTHORITY': str(empty)}, capture_output=True, timeout=10)
            require(good.returncode == 0 and bad.returncode != 0, 'X11_AUTH_FAILED')
            require(listeners() == before_ports, 'DISPLAY_LISTENER_CHANGE')
            run = subprocess.Popen(['node', 'tests/security/restricted_auth_synthetic.mjs'], cwd=ROOT,
                                   env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
            try:
                stdout, stderr = run.communicate(timeout=90)
            except subprocess.TimeoutExpired:
                os.killpg(run.pid, signal.SIGTERM)
                run.communicate(timeout=15)
                raise RuntimeError('SYNTHETIC_TIMEOUT')
            require(run.returncode == 0 and not stderr, 'SYNTHETIC_TEST_FAILED')
            evidence = json.loads(stdout)
            require(evidence.get('classification') == 'SYNTHETIC_BOUNDARY_PASS', 'SYNTHETIC_TEST_FAILED')
            require(evidence.get('output_leakage') is False and evidence.get('artifact_leakage') is False, 'SENTINEL_LEAK_STOP')
            result = {'synthetic': evidence, 'x11_authenticated': True, 'x11_unauthorized_rejected': True}
        finally:
            if xvfb is not None:
                xvfb.terminate()
                xvfb.wait(timeout=10)
        require(browser_pids() == before_browser, 'BROWSER_CLEANUP_FAILED')
        require(admin() == before_admin, 'ADMIN_CHANGED')
        require(listeners() == before_ports, 'LISTENER_CHANGE')
        require(not socket.exists() and not lock.exists(), 'DISPLAY_CLEANUP_FAILED')
    require(not Path(directory).exists(), 'TEMP_CLEANUP_FAILED')
    require(subprocess.run(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=ROOT, capture_output=True, check=True).stdout == before_git, 'REPOSITORY_CHANGED')
    result.update(repository_unchanged=True, admin_preserved=True, listeners_unchanged=True, browser_cleanup=True,
                  display_cleanup=True, temporary_files_removed=True,
                  port_9222_absent=not any(address.endswith(':9222') for _, address in listeners()))
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # No raw subprocess output, exception messages, X credentials or browser data.
        print(json.dumps({'classification': 'LAB_BLOCKED_OR_FAILED'}))
        raise SystemExit(1)
