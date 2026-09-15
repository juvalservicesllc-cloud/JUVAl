"""Temporary non-sensitive human viewer. No API for reading or driving VNC.

stdin CONFIRMED is a human visual attestation, not an automated browser action.
A page button supplies a separate synthetic interaction observation. Exits after
20 minutes, on stdin closure, STOP, or failure; owns only its child processes.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen

from restricted_auth_display_lab import ROOT, admin, listeners, browser_pids, require, write_authority

VNC = 5901
WEB = 6081
VIEWER_PORTS = {('tcp', f'127.0.0.1:{VNC}'), ('tcp', f'127.0.0.1:{WEB}')}
PAGE = b'''<!doctype html><meta charset="utf-8"><title>JUVAl synthetic viewer</title>
<h1>JUVAl PRIVATE VIEWER SYNTHETIC TEST</h1>
<p>No authentication. No secrets. Do not enter any credentials.</p>
<button onclick="fetch('/challenge',{method:'POST'}).then(()=>{this.textContent='SYNTHETIC INTERACTION CONFIRMED'})">Confirm synthetic interaction</button>'''


def viewer_commands(auth):
    return [
        ['x11vnc', '-display', ':100', '-auth', str(auth), '-listen', '127.0.0.1',
         '-rfbport', str(VNC), '-no6', '-forever', '-nopw', '-nosel', '-noprimary',
         '-nosetprimary', '-noclipboard', '-nosetclipboard', '-noremote'],
        ['websockify', '--web=/usr/share/novnc', f'127.0.0.1:{WEB}', f'127.0.0.1:{VNC}'],
    ]


def require_listener_delta(before, expected):
    require(listeners() == before | expected, 'UNEXPECTED_LISTENER')


def wait_for(check, processes, seconds=10):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        require(all(p.poll() is None for p in processes), 'CHILD_EXITED')
        if check():
            return
        time.sleep(.1)
    raise RuntimeError('START_TIMEOUT')


def stop_owned(process):
    """Stop only the exact child object created by this harness."""
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def protocol(proc, request=None):
    if request is not None:
        proc.stdin.write(json.dumps(request)+'\n')
        proc.stdin.flush()
    require(select.select([proc.stdout], [], [], 20)[0], 'CONTROLLER_TIMEOUT')
    value = json.loads(proc.stdout.readline())
    require(isinstance(value, dict) and set(value) == {'status', 'path'}, 'CONTROLLER_SCHEMA')
    require(value['status'] in {'READY', 'OBSERVED', 'CLOSED', 'REJECTED', 'FAILED'}, 'CONTROLLER_SCHEMA')
    require(value['path'] in {None, '/login', '/challenge', '/callback'}, 'CONTROLLER_SCHEMA')
    return value


def main():
    xsocket, xlock = Path('/tmp/.X11-unix/X100'), Path('/tmp/.X100-lock')
    require(not xsocket.exists() and not xlock.exists(), 'DISPLAY_BUSY')
    before_admin, before_ports = admin(), listeners()
    require(not browser_pids(), 'DEDICATED_BROWSER_BUSY')
    require(not any(a.rsplit(':', 1)[-1] in {'5901', '6081', '9222'} for _, a in before_ports), 'PORT_BUSY')
    before_git = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=ROOT, capture_output=True, check=True).stdout
    clicked, served = threading.Event(), threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            if self.path != '/login':
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(PAGE)
            served.set()

        def do_POST(self):
            if self.path != '/challenge':
                self.send_error(404)
                return
            clicked.set()  # Boolean only; never inspect request bodies or headers.
            self.send_response(204)
            self.end_headers()

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    fixture_port = server.server_address[1]
    expected = VIEWER_PORTS | {('tcp', f'127.0.0.1:{fixture_port}')}
    children, controller = [], None
    human_confirmed, ready, cleanup_ok = False, False, False
    stage = 'STARTING'
    with tempfile.TemporaryDirectory(prefix='juval-private-viewer-') as directory:
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
                                     '-nolisten', 'tcp', '-auth', str(auth)],
                                    env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            children.append(xvfb)
            wait_for(xsocket.exists, children)
            good = subprocess.run(['xdpyinfo', '-display', ':100'], env=env, capture_output=True, timeout=10)
            bad = subprocess.run(['xdpyinfo', '-display', ':100'], env={**env, 'XAUTHORITY': str(empty)}, capture_output=True, timeout=10)
            require(good.returncode == 0 and bad.returncode != 0, 'X11_AUTH_FAILED')
            for command in viewer_commands(auth):
                children.append(subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            wait_for(lambda: listeners() == before_ports | expected, children)
            # Protocol banner only; no framebuffer, clipboard or viewer input is read.
            with socket.create_connection(('127.0.0.1', VNC), timeout=5) as connection:
                require(connection.recv(12).startswith(b'RFB '), 'VNC_PROTOCOL')
            with urlopen(f'http://127.0.0.1:{WEB}/vnc.html', timeout=5) as response:
                require(response.status == 200, 'NOVNC_HTTP')
            controller = subprocess.Popen(['node', 'tools/restricted_auth_evidence.mjs'], cwd=ROOT,
                env={**env, 'JUVAL_SYNTHETIC_ORIGIN': f'http://127.0.0.1:{fixture_port}'},
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
            require(protocol(controller)['status'] == 'READY', 'CONTROLLER_START')
            require(protocol(controller, {'op': 'visit', 'state': 'login'}) ==
                    {'status': 'OBSERVED', 'path': '/login'}, 'SYNTHETIC_NAVIGATION')
            require(served.wait(5), 'PAGE_NOT_SERVED')
            require(browser_pids(), 'NO_DEDICATED_BROWSER')
            require(admin() == before_admin, 'ADMIN_CHANGED')
            require_listener_delta(before_ports, expected)
            ready = True
            stage = 'WAITING_FOR_HUMAN'
            print(json.dumps({'status': stage, 'display': ':100', 'vnc': '127.0.0.1:5901',
                              'novnc': 'http://127.0.0.1:6081/vnc.html?autoconnect=1&resize=scale',
                              'x11_auth_verified': True, 'clipboard_disabled': True,
                              'admin_unchanged': True, 'listeners_allowlisted': True}), flush=True)
            deadline = time.monotonic() + 1200
            while time.monotonic() < deadline:
                require(all(p.poll() is None for p in children) and controller.poll() is None, 'CHILD_EXITED')
                require(admin() == before_admin, 'ADMIN_CHANGED')
                require_listener_delta(before_ports, expected)
                if select.select([sys.stdin], [], [], 1)[0]:
                    line = sys.stdin.readline()
                    if line.strip() == 'CONFIRMED' and clicked.is_set():
                        human_confirmed = True
                        break
                    if not line or line.strip() == 'STOP':
                        break
            stage = 'CONFIRMED' if human_confirmed else 'UNCONFIRMED'
        except Exception:
            stage = 'FAILED'  # Never emit raw browser or viewer diagnostic content.
        finally:
            if controller is not None and controller.poll() is None:
                try:
                    require(protocol(controller, {'op': 'close'})['status'] == 'CLOSED', 'BROWSER_CLOSE')
                    controller.stdin.close()
                    controller.wait(timeout=15)
                except Exception:
                    stop_owned(controller)
            for process in reversed(children):
                stop_owned(process)
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            require(not browser_pids(), 'BROWSER_RESIDUAL')
            require(not xsocket.exists() and not xlock.exists(), 'DISPLAY_RESIDUAL')
            require(admin() == before_admin, 'ADMIN_CHANGED')
            require_listener_delta(before_ports, set())
            cleanup_ok = True
    require(not Path(directory).exists(), 'TEMP_RESIDUAL')
    after_git = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=ROOT, capture_output=True, check=True).stdout
    require(after_git == before_git, 'REPOSITORY_RUNTIME_CHANGE')
    print(json.dumps({'status': stage, 'runtime_ready': ready, 'human_confirmed': human_confirmed,
                      'synthetic_interaction': clicked.is_set(), 'cleanup': cleanup_ok,
                      'admin_unchanged': True, 'listeners_restored': True, 'repo_unchanged_by_runtime': True}), flush=True)
    return 0 if human_confirmed else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print('{"status":"FAILED_OR_CLEANUP_UNVERIFIED"}', flush=True)
        raise SystemExit(1)
