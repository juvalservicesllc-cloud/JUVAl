"""Opt-in real FusionAuth GET-only loopback lab; never mutates provider config.

Requires independently verified temporary redirect baseline/add/readback.
Operator MUST restore that redirect after success or failure. No access/error
logs, response bodies, cookies or OAuth query values are persisted by this lab.
"""
from __future__ import annotations

import argparse
import http.client
import json
from pathlib import Path
import subprocess
import tempfile
import time

from fusionauth_surface_discovery import probe_real_login, fetch
from nginx_surface_lab import (
    TEMPLATE, NGINX_CONF, render_lab_config, find_nginx, _free_port,
)


def verify_paths(observations):
    """Only the observed initial-page assets are required; conditional paths differ."""
    denied = {'/admin', '/api', '/account', '/password', '/password/forgot', '/oauth2/userinfo'}
    for item in observations:
        path, status = item['path'], item['status']
        if path in denied and status != 404:
            return False
        if path.startswith(('/css/', '/js/', '/images/')) and status != 200:
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--temporary-redirect-confirmed', action='store_true')
    args = parser.parse_args()
    if not args.temporary_redirect_confirmed:
        parser.error('independent baseline/add/readback required before this lab')
    binary = find_nginx()
    if not binary:
        print('BLOCKED: user-space nginx binary required')
        return 2
    process = None
    try:
        with tempfile.TemporaryDirectory(prefix='juval-real-nginx-') as scratch:
            port = _free_port()
            base = f'http://127.0.0.1:{port}'
            Path(scratch, 'juval-public.conf').write_text(
                render_lab_config(TEMPLATE.read_text(), port, 9011))
            config = NGINX_CONF.format(scratch=scratch)
            config = config.replace(f'access_log {scratch}/access.log;', 'access_log off;')
            config = config.replace(f'error_log {scratch}/error.log warn;', 'error_log /dev/null crit;')
            Path(scratch, 'nginx.conf').write_text(config)
            try:
                process = subprocess.Popen(
                    [binary, '-p', scratch, '-c', str(Path(scratch, 'nginx.conf')), '-e', '/dev/null'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                for _ in range(50):
                    if process.poll() is not None:
                        raise RuntimeError('nginx startup failed')
                    try:
                        fetch(base + '/admin')
                        break
                    except OSError:
                        time.sleep(.1)
                login = probe_real_login(base, temporary_redirect_confirmed=True)
                paths = sorted(set(login['resources']) | {
                    '/admin', '/api', '/account', '/password', '/oauth2/userinfo',
                    '/fonts/fontawesome-webfont.woff2', '/assets/icons/fingerprint-overlay.svg',
                    '/css', '/js', '/images', '/oauth2/two-factor', '/oauth2/two-factor-methods',
                })
                observations = []
                for path in paths:
                    response = fetch(base + path)
                    observations.append({'path': path, 'status': response.status,
                                         'mime': response.content_type})
                redirects = []
                for path in ('/css', '/js', '/images'):
                    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
                    try:
                        connection.request('GET', path + '?lab=1', headers={
                            'Host': 'attacker.invalid', 'X-Forwarded-Host': 'attacker.invalid',
                            'X-Forwarded-Proto': 'http', 'X-Forwarded-For': '192.0.2.1'})
                        response = connection.getresponse()
                        valid = response.status == 301 and response.getheader('Location') == path + '/?lab=1'
                        redirects.append({'path': path, 'hostile_headers_relative_redirect': valid})
                        response.read()
                    finally:
                        connection.close()
                rendered = (login['classification'] == 'OBSERVED_REAL_JUVAL_LOGIN'
                            and verify_paths(observations)
                            and all(row['hostile_headers_relative_redirect'] for row in redirects))
                result = {
                    'classification': 'RUNTIME_LOOPBACK_VERIFIED' if rendered else 'NOT_VERIFIED',
                    'scope': 'Initial authorize HTML and GET paths only; not MFA, WebAuthn or production',
                    'login': login, 'paths': observations, 'redirects': redirects,
                    'temporary_redirect_cleanup': 'REQUIRED_ADMIN_READBACK',
                }
                print(json.dumps(result, indent=2))
                return 0 if rendered else 1
            finally:
                if process is not None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
    except Exception:
        print('NOT_VERIFIED: loopback lab failed; diagnostics suppressed; redirect cleanup REQUIRED')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
