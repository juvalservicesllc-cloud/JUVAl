"""Behavioural laboratory for the planned public identity surface.

`deploy/fusionauth/nginx-fusionauth-public.conf` is an allow-list: eleven
`location` blocks, ten of which publish something and one of which answers 404
to everything else. Until now every claim about that file rested on reading it.
A configuration that parses is not a configuration that behaves, so this script
runs the real template under a real nginx and measures what it actually does.

What it does NOT do, deliberately:

* it never touches `/etc/nginx`, never installs anything, never runs as root
  and never opens a port outside `127.0.0.1`;
* it never contacts FusionAuth. The upstream is a disposable echo server, so
  nothing in this lab can read, write or even reach the production identity
  provider. `9011`/`9012` are never bound;
* it therefore cannot answer the two questions that actually block Phase 2 --
  whether FusionAuth 1.69.0 serves `/oauth2/two-factor` at all, and which asset
  paths its hosted pages request. Those need a fresh FusionAuth instance. This
  lab measures the *proxy*, not the *provider*, and the classification it
  emits says so.

What it can prove, and nothing had proved before: that the allow-list denies
what it claims to deny and that a denied request never reaches the upstream at
all; that each `limit_except` really rejects the methods it excludes; that the
forwarded headers arrive with the values FusionAuth builds its issuer from, and
that a client cannot override them; and that the query string an Authorization
Code flow depends on survives the proxy byte for byte.

Usage:
    python tools/nginx_surface_lab.py            # human-readable table
    python tools/nginx_surface_lab.py --json     # machine-readable
    JUVAL_NGINX_BIN=/path/to/nginx python tools/nginx_surface_lab.py

Exit code is non-zero if any probe fails, so it can gate CI. Stdlib only, and
no secret of any kind is read, written or printed -- the lab has no
credentials to leak, which is the point.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / "deploy" / "fusionauth" / "nginx-fusionauth-public.conf"

# The template's `include` names a file that deliberately does not live in the
# repository (it carries the public hostname, unknown until the Phase 2 tunnel
# exists). Without substituting it nginx refuses to start, so the lab supplies
# the one line that file is documented to contain.
HOST_INCLUDE = "include /etc/nginx/juval-fusionauth-host.conf;"
LAB_PUBLIC_HOST = "idp.lab.invalid"  # RFC 2606: cannot resolve, by construction

TEMPLATE_LISTEN = "listen 127.0.0.1:8080;"
TEMPLATE_UPSTREAM = "http://127.0.0.1:9011"

HTTP_TIMEOUT = 5
STARTUP_TIMEOUT = 15


# --- Rendering the shipped template into a runnable lab config -----------


def render_lab_config(template: str, listen_port: int, upstream_port: int) -> str:
    """Rewrite exactly three things and refuse to rewrite anything else.

    The value of this lab depends entirely on it exercising the *shipped*
    rules, so the substitution is narrow and self-checking: the listen address,
    the upstream address, and the hostname include. Every `location`,
    `limit_except`, `return` and `proxy_set_header` line must survive
    byte-identical, and this function asserts that before handing the config
    back. If the template ever grows a rule that needs rewriting to run here,
    that assertion fires rather than the lab quietly testing something else.
    """
    if HOST_INCLUDE not in template:
        raise ValueError(f"template no longer contains {HOST_INCLUDE!r}")
    if TEMPLATE_LISTEN not in template:
        raise ValueError(f"template no longer contains {TEMPLATE_LISTEN!r}")
    if TEMPLATE_UPSTREAM not in template:
        raise ValueError(f"template no longer proxies to {TEMPLATE_UPSTREAM!r}")

    rendered = template.replace(
        HOST_INCLUDE, f'set $juval_public_host "{LAB_PUBLIC_HOST}";'
    )
    rendered = rendered.replace(TEMPLATE_LISTEN, f"listen 127.0.0.1:{listen_port};")
    rendered = rendered.replace(
        TEMPLATE_UPSTREAM, f"http://127.0.0.1:{upstream_port}"
    )

    if _rule_lines(rendered) != _rule_lines(template):
        raise AssertionError("lab rendering altered a routing or header rule")
    return rendered


_RULE_DIRECTIVE = re.compile(
    r"^\s*(location|limit_except|return|proxy_set_header)\b", re.MULTILINE
)


def _rule_lines(config: str) -> list[str]:
    """The lines whose meaning the lab must not disturb."""
    return [
        line.strip()
        for line in config.splitlines()
        if _RULE_DIRECTIVE.match(line)
    ]


NGINX_CONF = """\
daemon off;
worker_processes 1;
pid {scratch}/nginx.pid;
error_log {scratch}/error.log warn;
events {{ worker_connections 64; }}
http {{
    access_log {scratch}/access.log;
    client_body_temp_path {scratch}/body;
    proxy_temp_path {scratch}/proxy;
    fastcgi_temp_path {scratch}/fastcgi;
    uwsgi_temp_path {scratch}/uwsgi;
    scgi_temp_path {scratch}/scgi;
    default_type application/octet-stream;
    include {scratch}/juval-public.conf;
}}
"""


# --- Disposable upstream (stands in for FusionAuth; never contacts it) ---


@dataclass
class SeenRequest:
    method: str
    target: str
    headers: dict[str, str]


class _EchoHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "juval-lab-upstream"
    sys_version = ""

    def log_message(self, *_args: Any) -> None:  # keep the lab output deterministic
        return

    def _record(self) -> bytes:
        seen = SeenRequest(
            method=self.command,
            target=self.path,
            headers={k.lower(): v for k, v in self.headers.items()},
        )
        self.server.seen.append(seen)  # type: ignore[attr-defined]
        return json.dumps(
            {"method": seen.method, "target": seen.target, "headers": seen.headers}
        ).encode()

    def _respond(self, body: bytes, *, with_body: bool) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if with_body:
            self.wfile.write(body)

    def _handle(self, *, with_body: bool = True) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self._respond(self._record(), with_body=with_body)

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _handle

    def do_HEAD(self) -> None:
        self._handle(with_body=False)


class EchoUpstream:
    """A throwaway HTTP server on loopback that records what reached it."""

    def __init__(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _EchoHandler)
        self._server.seen = []  # type: ignore[attr-defined]
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def seen(self) -> list[SeenRequest]:
        return self._server.seen  # type: ignore[attr-defined]

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


# --- The nginx instance --------------------------------------------------


def find_nginx() -> Optional[str]:
    """`JUVAL_NGINX_BIN` first, then PATH. Never installs anything."""
    override = os.environ.get("JUVAL_NGINX_BIN")
    if override:
        return override if Path(override).is_file() else None
    return shutil.which("nginx")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class NginxLab:
    """Runs the shipped template under a scratch-prefixed nginx.

    Everything it creates lives under one temporary directory and one child
    process, and both are torn down in `close()` even if a probe raised.
    """

    def __init__(self, binary: str, template_text: str) -> None:
        self.binary = binary
        self.template_text = template_text
        self.upstream = EchoUpstream()
        self.port = _free_port()
        self._scratch = Path(tempfile.mkdtemp(prefix="juval-nginx-lab-"))
        self._process: Optional[subprocess.Popen] = None

    @property
    def scratch(self) -> Path:
        return self._scratch

    @property
    def rendered_config(self) -> str:
        return (self._scratch / "juval-public.conf").read_text(encoding="utf-8")

    def start(self) -> None:
        self.upstream.start()
        (self._scratch / "juval-public.conf").write_text(
            render_lab_config(self.template_text, self.port, self.upstream.port),
            encoding="utf-8",
        )
        (self._scratch / "nginx.conf").write_text(
            NGINX_CONF.format(scratch=self._scratch), encoding="utf-8"
        )
        self._stderr = (self._scratch / "stderr.log").open("wb")
        self._process = subprocess.Popen(
            [
                self.binary,
                "-p",
                str(self._scratch),
                "-e",
                str(self._scratch / "error.log"),
                "-c",
                str(self._scratch / "nginx.conf"),
            ],
            stdout=self._stderr,
            stderr=subprocess.STDOUT,
        )
        self._await_listening()

    def config_test(self) -> subprocess.CompletedProcess:
        """`nginx -t` on the rendered config -- validity, not behaviour."""
        return subprocess.run(
            [
                self.binary,
                "-t",
                "-p",
                str(self._scratch),
                "-e",
                str(self._scratch / "error.log"),
                "-c",
                str(self._scratch / "nginx.conf"),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def _await_listening(self) -> None:
        deadline = time.monotonic() + STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            if self._process is not None and self._process.poll() is not None:
                raise RuntimeError(f"nginx exited early:\n{self._diagnostics()}")
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                    return
            except OSError:
                time.sleep(0.1)
        raise TimeoutError(f"nginx never listened:\n{self._diagnostics()}")

    def _diagnostics(self) -> str:
        parts = []
        for name in ("stderr.log", "error.log"):
            path = self._scratch / name
            if path.exists():
                parts.append(f"--- {name} ---\n{path.read_text(errors='replace')}")
        return "\n".join(parts)

    def request(
        self,
        method: str,
        target: str,
        headers: Optional[dict[str, str]] = None,
    ) -> tuple[int, dict[str, str], bytes]:
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.port, timeout=HTTP_TIMEOUT
        )
        try:
            connection.request(method, target, headers=headers or {})
            response = connection.getresponse()
            body = response.read()
            return (
                response.status,
                {k.lower(): v for k, v in response.getheaders()},
                body,
            )
        finally:
            connection.close()

    def close(self) -> None:
        if self._process is not None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=10)
            self._process = None
        if getattr(self, "_stderr", None) is not None:
            self._stderr.close()
        self.upstream.close()
        shutil.rmtree(self._scratch, ignore_errors=True)

    def __enter__(self) -> "NginxLab":
        self.start()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


# --- Probes --------------------------------------------------------------

PROXIED = "proxied"  # 200 from the echo upstream
DENIED_METHOD = "denied-method"  # 403 from limit_except, upstream untouched
NOT_PUBLISHED = "not-published"  # 404 from location /, upstream untouched
REDIRECTED = "redirected"  # 301 from nginx's prefix-location rule (finding N-1)
MALFORMED = "malformed"  # 400: rejected before location matching (finding N-2)


@dataclass(frozen=True)
class Probe:
    rule: str
    method: str
    target: str
    expect: str
    why: str
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def expected_status(self) -> int:
        return {
            PROXIED: 200,
            DENIED_METHOD: 403,
            NOT_PUBLISHED: 404,
            REDIRECTED: 301,
            MALFORMED: 400,
        }[self.expect]


AUTHORIZE_QUERY = (
    "?client_id=00000000-0000-0000-0000-000000000000&response_type=code"
    "&redirect_uri=https%3A%2F%2Fapp.example%2Fcb&scope=openid+profile"
    "&state=abc.123-_~&nonce=xyz&code_challenge=E9Me&code_challenge_method=S256"
)

PROBES: tuple[Probe, ...] = (
    # --- the five protocol-justified exact routes ---
    Probe("/.well-known/openid-configuration", "GET", "/.well-known/openid-configuration", PROXIED, "discovery is read by tools/verify_oidc.py"),
    Probe("/.well-known/openid-configuration", "HEAD", "/.well-known/openid-configuration", PROXIED, "limit_except GET admits HEAD -- measure, do not assume"),
    Probe("/.well-known/openid-configuration", "POST", "/.well-known/openid-configuration", DENIED_METHOD, "metadata is read-only"),
    Probe("/.well-known/jwks.json", "GET", "/.well-known/jwks.json", PROXIED, "interfaces/api/auth.py resolves signing keys here"),
    Probe("/.well-known/jwks.json", "POST", "/.well-known/jwks.json", DENIED_METHOD, "metadata is read-only"),
    Probe("/oauth2/authorize", "GET", "/oauth2/authorize" + AUTHORIZE_QUERY, PROXIED, "renders the hosted login page"),
    Probe("/oauth2/authorize", "POST", "/oauth2/authorize" + AUTHORIZE_QUERY, PROXIED, "the hosted form posts credentials back to the same path"),
    Probe("/oauth2/authorize", "DELETE", "/oauth2/authorize", DENIED_METHOD, "only GET and POST are in the flow"),
    Probe("/oauth2/token", "POST", "/oauth2/token", PROXIED, "server-to-server code exchange"),
    Probe("/oauth2/token", "GET", "/oauth2/token", DENIED_METHOD, "a token endpoint reachable by navigation is a mistake"),
    Probe("/oauth2/logout", "GET", "/oauth2/logout", PROXIED, "browser navigation ends the SSO session"),
    Probe("/oauth2/logout", "POST", "/oauth2/logout", DENIED_METHOD, "logout is navigation, not submission"),
    # --- the five rules the template marks NOT_VERIFIED ---
    # The lab measures that the proxy dispatches them as written. Whether
    # FusionAuth serves them, and whether these are the right asset prefixes,
    # is a question about the provider and stays NOT_VERIFIED.
    Probe("/oauth2/two-factor", "GET", "/oauth2/two-factor", PROXIED, "dispatch only -- provider behaviour unmeasured"),
    Probe("/oauth2/two-factor", "POST", "/oauth2/two-factor", PROXIED, "dispatch only -- provider behaviour unmeasured"),
    Probe("/oauth2/two-factor", "PUT", "/oauth2/two-factor", DENIED_METHOD, "limit_except GET POST"),
    Probe("/oauth2/two-factor-methods", "GET", "/oauth2/two-factor-methods", PROXIED, "dispatch only -- provider behaviour unmeasured"),
    Probe("/oauth2/two-factor-methods", "POST", "/oauth2/two-factor-methods", PROXIED, "dispatch only -- provider behaviour unmeasured"),
    Probe("^~ /css/", "GET", "/css/style.css", PROXIED, "dispatch only -- the prefix hypothesis is unmeasured"),
    Probe("^~ /css/", "POST", "/css/style.css", DENIED_METHOD, "assets are GET-only"),
    Probe("^~ /js/", "GET", "/js/app.js", PROXIED, "dispatch only -- the prefix hypothesis is unmeasured"),
    Probe("^~ /images/", "GET", "/images/logo.png", PROXIED, "dispatch only -- the prefix hypothesis is unmeasured"),
    # --- matching precision: exact means exact ---
    Probe("location /", "GET", "/oauth2/authorize/", NOT_PUBLISHED, "trailing slash is a different URI than the exact match"),
    Probe("location /", "GET", "/oauth2/authorizex", NOT_PUBLISHED, "an exact location must not behave as a prefix"),
    Probe("location /", "GET", "/oauth2/token/x", NOT_PUBLISHED, "an exact location must not behave as a prefix"),
    # Finding N-1, measured not assumed: the template's inventory says
    # "Everything else: 404", and for these three URIs that is false. nginx
    # answers a prefix location that ends in a slash and proxies with a 301 to
    # the slashed form, built from the *client's* Host header. See
    # measure_bare_prefix_redirect().
    Probe("^~ /css/", "GET", "/css", REDIRECTED, "prefix-with-slash + proxy_pass emits 301, not 404"),
    Probe("^~ /js/", "GET", "/js", REDIRECTED, "same rule"),
    Probe("^~ /images/", "GET", "/images", REDIRECTED, "same rule"),
    Probe("location /", "GET", "/OAuth2/authorize", NOT_PUBLISHED, "nginx location matching is case-sensitive"),
    Probe("location /", "GET", "/.well-known/", NOT_PUBLISHED, "the well-known directory itself is not published"),
    Probe("location /", "GET", "/.well-known/security.txt", NOT_PUBLISHED, "only two well-known documents are published"),
    # --- the never-publish list (ADR-035 Condition 2) ---
    Probe("location /", "GET", "/", NOT_PUBLISHED, "the root is not a JUVAl surface"),
    Probe("location /", "GET", "/admin", NOT_PUBLISHED, "FusionAuth administrative UI"),
    Probe("location /", "GET", "/admin/", NOT_PUBLISHED, "FusionAuth administrative UI"),
    Probe("location /", "GET", "/admin/login", NOT_PUBLISHED, "FusionAuth administrative UI"),
    Probe("location /", "POST", "/admin/login", NOT_PUBLISHED, "a denied path is denied for every method"),
    Probe("location /", "GET", "/api", NOT_PUBLISHED, "FusionAuth REST API"),
    Probe("location /", "GET", "/api/user", NOT_PUBLISHED, "FusionAuth REST API"),
    Probe("location /", "POST", "/api/user", NOT_PUBLISHED, "user creation must never be reachable"),
    Probe("location /", "GET", "/api/status", NOT_PUBLISHED, "FusionAuth REST API"),
    Probe("location /", "GET", "/account", NOT_PUBLISHED, "self-service portal answers 200 on Community"),
    Probe("location /", "GET", "/account/", NOT_PUBLISHED, "self-service portal"),
    Probe("location /", "GET", "/password/forgot", NOT_PUBLISHED, "ADR-035 Condition 2"),
    Probe("location /", "GET", "/password/change", NOT_PUBLISHED, "JUVAl never sets passwordChangeRequired"),
    Probe("location /", "GET", "/oauth2/register", NOT_PUBLISHED, "self-registration is not a JUVAl flow"),
    Probe("location /", "GET", "/oauth2/passwordless", NOT_PUBLISHED, "unused flow"),
    Probe("location /", "GET", "/oauth2/device", NOT_PUBLISHED, "unused flow"),
    Probe("location /", "GET", "/oauth2/consent", NOT_PUBLISHED, "unused flow"),
    Probe("location /", "GET", "/oauth2/start-idp-link", NOT_PUBLISHED, "unused flow"),
    Probe("location /", "GET", "/oauth2/two-factor-enable", NOT_PUBLISHED, "JUVAl pre-attaches the factor; self-enrolment has no user"),
    Probe("location /", "GET", "/oauth2/two-factor-enable-complete", NOT_PUBLISHED, "as above"),
    # --- normalisation: a denied path must stay denied however it is spelt ---
    Probe("location /", "GET", "/css/../admin", NOT_PUBLISHED, "traversal out of an allowed prefix must not reach /admin"),
    Probe("location /", "GET", "/css/%2e%2e/admin", NOT_PUBLISHED, "percent-encoded traversal must not reach /admin"),
    Probe("location /", "GET", "/css/./../admin", NOT_PUBLISHED, "dot-segment traversal must not reach /admin"),
    Probe("location /", "GET", "//admin", NOT_PUBLISHED, "duplicate slashes must not evade the catch-all"),
    Probe("location /", "GET", "/admin?next=/css/x.css", NOT_PUBLISHED, "the query string must not influence matching"),
    # Finding N-2: traversal *above* the root is rejected at 400 before any
    # location is chosen. Fail-closed, and stronger than the 404 originally
    # expected -- recorded because the difference is the interesting part.
    Probe("(pre-routing)", "GET", "/js/../../api/user", MALFORMED, "traversal above root is rejected before routing"),
    Probe("(pre-routing)", "GET", "/../admin", MALFORMED, "traversal above root is rejected before routing"),
    Probe("(pre-routing)", "GET", "/%2e%2e/admin", MALFORMED, "encoded traversal above root is rejected before routing"),
    # CORS preflight against the token endpoint: the BFF calls it
    # server-to-server, so a browser must never be told it may.
    Probe("/oauth2/token", "OPTIONS", "/oauth2/token", DENIED_METHOD, "no browser-side use of the token endpoint"),
)


@dataclass
class ProbeResult:
    probe: Probe
    status: int
    reached_upstream: bool
    detail: str

    @property
    def ok(self) -> bool:
        if self.status != self.probe.expected_status:
            return False
        # A denied request that still reached the upstream is a failure even
        # when the client saw the right status: the point of an allow-list is
        # that the provider never sees the request.
        return self.reached_upstream is (self.probe.expect == PROXIED)


def run_probes(lab: NginxLab) -> list[ProbeResult]:
    results = []
    for probe in PROBES:
        before = len(lab.upstream.seen)
        status, _headers, _body = lab.request(probe.method, probe.target, probe.headers)
        reached = len(lab.upstream.seen) > before
        detail = ""
        if reached:
            seen = lab.upstream.seen[-1]
            detail = f"upstream saw {seen.method} {seen.target}"
        results.append(ProbeResult(probe, status, reached, detail))
    return results


# --- Forwarded-header and query-preservation measurements ----------------


def measure_forwarding(lab: NginxLab) -> dict[str, Any]:
    """What the upstream actually receives on an allowed route.

    FusionAuth builds absolute URLs -- the issuer among them -- from these
    headers, so a client that could influence them could influence the issuer.
    The probe sends hostile values for every one of them.
    """
    before = len(lab.upstream.seen)
    lab.request(
        "GET",
        "/oauth2/authorize" + AUTHORIZE_QUERY,
        {
            "Host": "attacker.example",
            "X-Forwarded-Proto": "http",
            "X-Forwarded-Host": "attacker.example",
            "X-Forwarded-Port": "80",
            "X-Forwarded-For": "203.0.113.9",
        },
    )
    if len(lab.upstream.seen) == before:
        raise AssertionError("/oauth2/authorize did not reach the upstream")
    seen = lab.upstream.seen[-1]
    return {
        "target": seen.target,
        "host": seen.headers.get("host"),
        "x-forwarded-host": seen.headers.get("x-forwarded-host"),
        "x-forwarded-proto": seen.headers.get("x-forwarded-proto"),
        "x-forwarded-port": seen.headers.get("x-forwarded-port"),
        "x-forwarded-for": seen.headers.get("x-forwarded-for"),
    }


def measure_bare_prefix_redirect(lab: NginxLab) -> dict[str, Any]:
    """Finding N-1: where the 301 for `/css` points, and who controls it.

    nginx's documented rule -- a prefix location ending in a slash whose
    requests are handled by `proxy_pass` answers the unslashed URI with a 301 --
    means three URIs on this surface are not 404. The redirect target is
    assembled from `$host`, i.e. the client's own `Host` header, plus the
    listener's scheme and port. `proxy_set_header Host` cannot affect it: the
    redirect is generated before anything is proxied.
    """
    status, headers, _body = lab.request(
        "GET", "/css", {"Host": "attacker.example"}
    )
    return {
        "status": status,
        "location": headers.get("location", ""),
        "reflects_client_host": "attacker.example" in headers.get("location", ""),
        "scheme_is_http": headers.get("location", "").startswith("http://"),
        "leaks_listen_port": f":{lab.port}" in headers.get("location", ""),
    }


def measure_missing_host_include(binary: str, template: str) -> dict[str, Any]:
    """Fail-closed check: the template cannot be enabled without the include.

    `/etc/nginx/juval-fusionauth-host.conf` is intentionally absent from the
    repository. If nginx accepted the file without it, `$juval_public_host`
    would expand to the empty string and FusionAuth would build an issuer with
    a blank host. It does not accept it, and that is worth pinning.
    """
    scratch = Path(tempfile.mkdtemp(prefix="juval-nginx-lab-noinc-"))
    try:
        broken = template.replace(HOST_INCLUDE, "# include removed for this check")
        broken = broken.replace(TEMPLATE_LISTEN, "listen 127.0.0.1:1;")
        (scratch / "juval-public.conf").write_text(broken, encoding="utf-8")
        (scratch / "nginx.conf").write_text(
            NGINX_CONF.format(scratch=scratch), encoding="utf-8"
        )
        result = subprocess.run(
            [binary, "-t", "-p", str(scratch), "-e", str(scratch / "error.log"),
             "-c", str(scratch / "nginx.conf")],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "config_test_rejected": result.returncode != 0,
            "names_the_variable": "juval_public_host" in result.stderr,
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def measure_denied_response(lab: NginxLab) -> dict[str, Any]:
    """What a rejected client learns about the host from the 404 itself."""
    status, headers, body = lab.request("GET", "/admin")
    return {
        "status": status,
        "server_header": headers.get("server", ""),
        "body_names_nginx": b"nginx" in body.lower(),
        "security_headers": sorted(
            name
            for name in headers
            if name
            in {
                "strict-transport-security",
                "x-frame-options",
                "x-content-type-options",
                "content-security-policy",
                "referrer-policy",
            }
        ),
    }


# --- Entry point ---------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    binary = find_nginx()
    if binary is None:
        print(
            "BLOCKED  no nginx binary. Set JUVAL_NGINX_BIN or put nginx on PATH.\n"
            "         A user-space binary is enough; no installation is required.",
            file=sys.stderr,
        )
        return 2

    template_text = TEMPLATE.read_text(encoding="utf-8")
    with NginxLab(binary, template_text) as lab:
        config_test = lab.config_test()
        results = run_probes(lab)
        forwarding = measure_forwarding(lab)
        redirect = measure_bare_prefix_redirect(lab)
        denied = measure_denied_response(lab)
    missing_include = measure_missing_host_include(binary, template_text)

    failures = [r for r in results if not r.ok]

    if args.json:
        print(
            json.dumps(
                {
                    "nginx": binary,
                    "config_test_ok": config_test.returncode == 0,
                    "probes": [
                        {
                            "rule": r.probe.rule,
                            "method": r.probe.method,
                            "target": r.probe.target,
                            "expect": r.probe.expect,
                            "status": r.status,
                            "reached_upstream": r.reached_upstream,
                            "ok": r.ok,
                        }
                        for r in results
                    ],
                    "forwarding": forwarding,
                    "bare_prefix_redirect": redirect,
                    "missing_host_include": missing_include,
                    "denied_response": denied,
                    "failures": len(failures),
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        width = max(len(f"{r.probe.method} {r.probe.target}") for r in results)
        for result in results:
            verdict = "PASS" if result.ok else "FAIL"
            request = f"{result.probe.method} {result.probe.target}"
            upstream = "->upstream" if result.reached_upstream else "  blocked "
            print(
                f"{verdict}  {request:<{width}}  {result.status}  {upstream}  "
                f"{result.probe.expect}"
            )
        print()
        print(f"config test         : {'ok' if config_test.returncode == 0 else 'FAILED'}")
        for key, value in sorted(forwarding.items()):
            print(f"forwarded {key:<18}: {value}")
        for key, value in sorted(redirect.items()):
            print(f"redirect  {key:<18}: {value}")
        for key, value in sorted(missing_include.items()):
            print(f"no-include {key:<17}: {value}")
        for key, value in sorted(denied.items()):
            print(f"denied    {key:<18}: {value}")
        print()
        print(f"{len(results) - len(failures)}/{len(results)} probes passed")

    return 1 if failures or config_test.returncode != 0 else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
