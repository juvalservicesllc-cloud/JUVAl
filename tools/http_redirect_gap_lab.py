"""Bounded synthetic protocol redirect acceptance. No FusionAuth, viewer or real callback port.

Exit 2 is a measured containment failure, not a passing security gate.
Only finite counters/booleans are exported; raw child output/errors are withheld.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from restricted_auth_display_lab import ROOT, admin, browser_pids, listeners, require, write_authority
from private_viewer_lab import stop_owned

SENTINEL = b'SYNTHETIC_REDIRECT_CODE_SENTINEL'


def validate_evidence(evidence):
    require(isinstance(evidence, dict) and set(evidence) == {
        'classification', 'direct', 'redirect', 'browser_closed', 'servers_closed', 'setup_failure'}, 'SCHEMA')
    require(evidence['classification'] in {
        'GAP_REPRODUCED_CONTAINMENT_BLOCKED', 'PROTOCOL_CALLBACK_CONTAINMENT_PASS',
        'REPRODUCER_INCONCLUSIVE'}, 'SCHEMA')
    require(evidence['setup_failure'] in (None, 'OWNERSHIP', 'PIPE_CHECK', 'PAGE_SESSION',
                                         'ROOT_TARGET_GUARD', 'CHILD_TARGET_GUARD', 'OWNED_TARGET_PAUSED',
                                         'OTHER_TARGET_ATTACHED', 'EXPECTED_TARGET_NOT_PAGE', 'OTHER_TARGET_PAGE',
                                         'OTHER_TARGET_IFRAME', 'OTHER_TARGET_OTHER', 'OTHER_TARGET_BROWSER', 'OTHER_TARGET_TAB',
                                         'OTHER_TARGET_SERVICE_WORKER', 'OTHER_TARGET_WORKER', 'PREEXISTING_TARGET_CLOSE', 'WEBSOCKET_GUARD', 'FETCH_ENABLE'), 'SCHEMA')
    for key in ('browser_closed', 'servers_closed'):
        require(type(evidence[key]) is bool, 'SCHEMA')
    for mode in ('direct', 'redirect'):
        row = evidence[mode]
        booleans = {'navigation_attempted', 'code_crossed_boundary',
                    'sensor_observation_complete', 'finite_controller_callback',
                    'callback_protocol_intercepted', 'redirect_protocol_intercepted',
                    'protocol_pipe_only', 'protocol_failed'}
        counts = {'callback_request_event', 'callback_tcp_connections',
                  'callback_http_requests', 'source_http_redirects', 'callback_application_bytes'}
        require(isinstance(row, dict) and set(row) == booleans | counts, 'SCHEMA')
        require(all(type(row[k]) is bool for k in booleans), 'SCHEMA')
        require(all(type(row[k]) is int and 0 <= row[k] <= (409600 if k == 'callback_application_bytes' else 100) for k in counts), 'SCHEMA')


def main():
    require(len(sys.argv) == 1, 'ARGUMENTS')
    xsocket, xlock = Path('/tmp/.X11-unix/X100'), Path('/tmp/.X100-lock')
    require(not xsocket.exists() and not xlock.exists(), 'DISPLAY_BUSY')
    before_admin, before_ports = admin(), listeners()
    require(not browser_pids(), 'BROWSER_BUSY')
    require(not any(a.rsplit(':', 1)[-1] in {'18080', '5901', '6081', '9222'}
                    for _, a in before_ports), 'PORT_BUSY')
    before_git = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=ROOT)
    child = xvfb = None
    evidence = {'classification': 'REPRODUCER_INCONCLUSIVE'}
    stdout = stderr = b''
    artifact_files, artifact_matches = 0, 0
    exit_code = 1
    with tempfile.TemporaryDirectory(prefix='juval-http-redirect-') as directory:
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
            for _ in range(100):
                if xsocket.exists() or xvfb.poll() is not None:
                    break
                time.sleep(.05)
            require(xvfb.poll() is None and xsocket.exists(), 'DISPLAY_START')
            good = subprocess.run(['xdpyinfo', '-display', ':100'], env=env, capture_output=True, timeout=10)
            bad = subprocess.run(['xdpyinfo', '-display', ':100'], env={**env, 'XAUTHORITY': str(empty)}, capture_output=True, timeout=10)
            require(good.returncode == 0 and bad.returncode != 0, 'X11_AUTH')
            require(listeners() == before_ports, 'LISTENER_CHANGE')
            child = subprocess.Popen(['node', 'tests/security/http_redirect_gap.mjs'], cwd=ROOT,
                                     env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, start_new_session=True)
            try:
                deadline = time.monotonic() + 45
                while True:
                    require(not any(a.rsplit(':', 1)[-1] == '9222' for _, a in listeners()), 'CDP_TCP')
                    try:
                        stdout, stderr = child.communicate(timeout=min(.1, max(.01, deadline - time.monotonic())))
                        break
                    except subprocess.TimeoutExpired:
                        if time.monotonic() >= deadline:
                            raise
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGTERM)
                stdout, stderr = child.communicate(timeout=15)
                raise RuntimeError('TIMEOUT')
            require(SENTINEL not in stdout and SENTINEL not in stderr and not stderr, 'OUTPUT_STOP')
            evidence = json.loads(stdout)
            validate_evidence(evidence)
            exit_code = child.returncode
            require(exit_code in (0, 1, 2), 'EXIT')
        finally:
            if child is not None and child.poll() is None:
                stop_owned(child)
            if xvfb is not None:
                stop_owned(xvfb)
        require(not browser_pids(), 'BROWSER_RESIDUAL')
        require(not xsocket.exists() and not xlock.exists(), 'DISPLAY_RESIDUAL')
        require(admin() == before_admin and listeners() == before_ports, 'BASELINE_CHANGE')
        # Only owned synthetic runtime files, after browser exit; never Admin or auth files.
        for path in runtime.rglob('*'):
            if path.is_file() and not path.is_symlink():
                artifact_files += 1
                artifact_matches += SENTINEL in path.read_bytes()
    require(not Path(directory).exists(), 'TEMP_RESIDUAL')
    require(subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=ROOT) == before_git, 'GIT_CHANGE')
    print(json.dumps({'synthetic': evidence, 'x11_authenticated': True,
                      'output_sentinel_found': SENTINEL in stdout or SENTINEL in stderr,
                      'post_close_artifact_files': artifact_files,
                      'post_close_artifact_matches': artifact_matches,
                      'browser_display_temp_cleanup': True, 'listeners_restored': True,
                      'admin_metadata_unchanged': True, 'repository_unchanged_by_runtime': True, 'port_9222_absent_during_polling': True}))
    return exit_code if not artifact_matches else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print('{"classification":"REPRODUCER_FAILED_OR_CLEANUP_UNVERIFIED"}')
        raise SystemExit(1)
