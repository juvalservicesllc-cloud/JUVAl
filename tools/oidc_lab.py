"""Synthetic OIDC provider for local integration (SEC-01F). Never production.

A loopback-only stand-in for FusionAuth so the real BFF, verifier and
session store can be exercised end to end without any real identity,
credential or network. It implements only what JUVAl uses, with the same
rules a real provider must enforce:

* discovery and JWKS (RS256, one generated key per process, with `kid`);
* authorization code + PKCE: exact registered `redirect_uri`, `S256` only,
  single-use codes that expire, client secret compared in constant time;
* refresh tokens with rotation (a used refresh token is rejected);
* logout redirecting only to the registered post-logout URI.

Users are fixed synthetic identities chosen on a plain HTML page -- there is
no password. In-process hooks (`set_roles`, `disable`) simulate a role change
or a deactivated account at the IdP. Keys and tokens exist only in memory.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import secrets
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

LOOPBACK = "127.0.0.1"


@dataclass
class LabUser:
    sub: str
    name: str
    roles: list[str]
    enabled: bool = True


@dataclass
class _Code:
    sub: str
    redirect_uri: str
    nonce: str
    challenge: str
    expires: float


@dataclass
class SyntheticIdP:
    client_id: str
    client_secret: str
    redirect_uri: str
    post_logout_redirect_uri: str
    users: dict[str, LabUser]
    token_ttl: int = 300
    issue_refresh_tokens: bool = True
    port: int = 0
    _codes: dict = field(default_factory=dict)
    _refresh: dict = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self._key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._kid = "lab-" + secrets.token_hex(4)
        self._thread: threading.Thread | None = None
        try:
            self._server = ThreadingHTTPServer((LOOPBACK, self.port), _handler(self))
        except OSError:
            raise SystemExit(f"BLOCKED: synthetic IdP cannot bind {LOOPBACK}:{self.port} (port in use?)") from None
        self.port = self._server.server_address[1]
        self.issuer = f"http://localhost:{self.port}"

    # -- lifecycle and test hooks ---------------------------------------------

    def start(self) -> "SyntheticIdP":
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        # shutdown() waits for serve_forever(); on a server that never started it would block forever.
        if self._thread is not None:
            self._server.shutdown()
            self._thread = None
        self._server.server_close()

    def set_roles(self, sub: str, roles: list[str]) -> None:
        self.users[sub].roles = list(roles)

    def disable(self, sub: str) -> None:
        self.users[sub].enabled = False

    # -- protocol ---------------------------------------------------------------

    def discovery(self) -> dict:
        return {
            "issuer": self.issuer,
            "authorization_endpoint": f"{self.issuer}/oauth2/authorize",
            "token_endpoint": f"{self.issuer}/oauth2/token",
            "jwks_uri": f"{self.issuer}/.well-known/jwks.json",
            "end_session_endpoint": f"{self.issuer}/oauth2/logout",
            "response_types_supported": ["code"],
            "code_challenge_methods_supported": ["S256"],
            "id_token_signing_alg_values_supported": ["RS256"],
        }

    def jwks(self) -> dict:
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self._key.public_key()))
        return {"keys": [{**jwk, "kid": self._kid, "alg": "RS256", "use": "sig"}]}

    def authorize_error(self, query: dict) -> str | None:
        """Why an authorization request is refused, or None. Never redirects on error."""
        if query.get("client_id") != self.client_id:
            return "unknown client_id"
        if query.get("redirect_uri") != self.redirect_uri:
            return "redirect_uri is not registered"
        if query.get("response_type") != "code":
            return "only response_type=code"
        if query.get("code_challenge_method") != "S256" or not query.get("code_challenge"):
            return "PKCE S256 is required"
        if not query.get("state") or not query.get("nonce"):
            return "state and nonce are required"
        return None

    def issue_code(self, query: dict, sub: str) -> str:
        user = self.users.get(sub)
        if user is None or not user.enabled:
            raise PermissionError("unknown or disabled user")
        code = secrets.token_urlsafe(32)
        with self._lock:
            self._codes[code] = _Code(sub, query["redirect_uri"], query["nonce"], query["code_challenge"],
                                      time.time() + 60)
        return f"{self.redirect_uri}?" + urllib.parse.urlencode({"code": code, "state": query["state"]})

    def token(self, form: dict) -> tuple[int, dict]:
        if form.get("client_id") != self.client_id or not hmac.compare_digest(
                form.get("client_secret", ""), self.client_secret):
            return 401, {"error": "invalid_client"}
        grant = form.get("grant_type")
        if grant == "authorization_code":
            with self._lock:
                code = self._codes.pop(form.get("code", ""), None)        # single use
            verifier = form.get("code_verifier", "")
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
            if (code is None or code.expires < time.time() or code.redirect_uri != form.get("redirect_uri")
                    or not hmac.compare_digest(challenge, code.challenge)):
                return 400, {"error": "invalid_grant"}
            return 200, self._tokens(code.sub, nonce=code.nonce)
        if grant == "refresh_token":
            with self._lock:
                sub = self._refresh.pop(form.get("refresh_token", ""), None)  # rotation
            if sub is None or not self.users[sub].enabled:
                return 400, {"error": "invalid_grant"}
            return 200, self._tokens(sub)
        return 400, {"error": "unsupported_grant_type"}

    def _tokens(self, sub: str, nonce: str | None = None) -> dict:
        now = int(time.time())
        user = self.users[sub]
        claims = {"iss": self.issuer, "aud": self.client_id, "sub": sub, "iat": now,
                  "exp": now + self.token_ttl, "roles": list(user.roles)}
        sign = lambda c: jwt.encode(c, self._key, algorithm="RS256", headers={"kid": self._kid})  # noqa: E731
        response = {"token_type": "Bearer", "expires_in": self.token_ttl, "access_token": sign(claims)}
        if nonce is not None:
            response["id_token"] = sign({**claims, "nonce": nonce, "name": user.name})
        if self.issue_refresh_tokens:
            refresh = secrets.token_urlsafe(32)
            with self._lock:
                self._refresh[refresh] = sub
            response["refresh_token"] = refresh
        return response


def _handler(idp: SyntheticIdP):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, body, content_type="application/json", headers=()):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            for name, value in headers:
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _form(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            return dict(urllib.parse.parse_qsl(self.rfile.read(length).decode()))

        def do_GET(self):
            url = urllib.parse.urlsplit(self.path)
            query = dict(urllib.parse.parse_qsl(url.query))
            if url.path == "/.well-known/openid-configuration":
                return self._send(200, idp.discovery())
            if url.path == "/.well-known/jwks.json":
                return self._send(200, idp.jwks())
            if url.path == "/oauth2/authorize":
                error = idp.authorize_error(query)
                if error:
                    return self._send(400, {"error": "invalid_request", "error_description": error})
                hidden = "".join(f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(v)}">'
                                 for k, v in query.items())
                buttons = "".join(
                    f'<button name="user" value="{html.escape(u.sub)}">{html.escape(u.name)} '
                    f'({html.escape(", ".join(u.roles) or "no roles")})</button><br>'
                    for u in idp.users.values() if u.enabled)
                page = (f"<!doctype html><title>JUVAl synthetic IdP</title><h1>Synthetic sign-in (lab)</h1>"
                        f'<form method="post" action="/oauth2/authorize">{hidden}{buttons}</form>')
                return self._send(200, page.encode(), "text/html; charset=utf-8")
            if url.path == "/oauth2/logout":
                target = query.get("post_logout_redirect_uri")
                if query.get("client_id") != idp.client_id or target != idp.post_logout_redirect_uri:
                    return self._send(400, {"error": "invalid_request"})
                return self._send(302, b"", headers=[("Location", target)])
            return self._send(404, {"error": "not_found"})

        def do_POST(self):
            path = urllib.parse.urlsplit(self.path).path
            form = self._form()
            if path == "/oauth2/authorize":
                if idp.authorize_error(form):
                    return self._send(400, {"error": "invalid_request"})
                try:
                    location = idp.issue_code(form, form.get("user", ""))
                except PermissionError:
                    return self._send(403, {"error": "access_denied"})
                return self._send(302, b"", headers=[("Location", location)])
            if path == "/oauth2/token":
                status, body = idp.token(form)
                return self._send(status, body)
            return self._send(404, {"error": "not_found"})

        def log_message(self, *args):
            pass

    return Handler
