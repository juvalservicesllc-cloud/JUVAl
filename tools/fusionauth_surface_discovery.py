"""Read-only discovery of the public surface FusionAuth actually serves.

`deploy/fusionauth/nginx-fusionauth-public.conf` publishes three asset
prefixes -- `/css/`, `/js/`, `/images/` -- on a hypothesis nobody has tested,
and 404s everything else. Widening or narrowing that allow-list needs evidence
about what FusionAuth's hosted pages actually request. This tool collects that
evidence without touching a single byte of FusionAuth state.

Strictly read-only, and structurally so rather than by good intentions:

* **GET and HEAD only.** `fetch()` raises on any other method; there is no code
  path that can POST, PUT or DELETE.
* **Loopback only.** `fetch()` raises unless the host is a literal loopback IP, so it cannot reach a remote identity provider even by typo.
* **No credentials.** No API key is read, no client secret is accepted, no
  password or TOTP is handled, and no authenticated flow is attempted. The
  tool cannot log in.
* **No secrets printed.** Cookie values are never emitted -- only
  `SET_COOKIE_PRESENT = YES/NO`. All query values except numeric version metadata
  (including unknown names and nested redirect URLs) are replaced with
  `<redacted>` in every URL this tool prints. Route *structure* is the output;
  secret material is not.

What it cannot do, and does not pretend to: it observes whatever page the
running instance happens to render. One page render is not the complete
FusionAuth surface, and it is not evidence about a future FusionAuth version.
`classify_prefix()` returns INSUFFICIENT_EVIDENCE rather than a verdict when
the observed sample cannot support one.

Usage:
    python tools/fusionauth_surface_discovery.py                 # text report
    python tools/fusionauth_surface_discovery.py --json
    python tools/fusionauth_surface_discovery.py --base http://127.0.0.1:9011

Exit code: 0 on a completed pass, 2 if the instance is unreachable.
Stdlib only.
"""

from __future__ import annotations

import argparse
import html
import ipaddress
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Iterable, Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

TIMEOUT = 5
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
SAFE_METHODS = frozenset({"GET", "HEAD"})

# Query parameter names whose *values* must never be printed. Names are kept:
# the shape of a redirect is the finding, its secrets are not.
SENSITIVE_PARAMS = frozenset(
    {
        "state",
        "nonce",
        "code",
        "token",
        "access_token",
        "id_token",
        "refresh_token",
        "client_id",
        "client_secret",
        "code_challenge",
        "code_verifier",
        "tenantId",
        "userId",
        "loginId",
        "sessionId",
        "twoFactorId",
        "password",
    }
)

REDACTED = "<redacted>"

# The three prefixes the nginx template publishes on an untested hypothesis.
PUBLISHED_PREFIXES = ("/css/", "/js/", "/images/")

# Classifications for a prefix, from Task 6.
REQUIRED_AS_PREFIX = "REQUIRED_AS_PREFIX"
CAN_NARROW = "CAN_NARROW"
CAN_REPLACE_WITH_EXACT_PATHS = "CAN_REPLACE_WITH_EXACT_PATHS"
NOT_OBSERVED = "NOT_OBSERVED"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


# --- Sanitising ----------------------------------------------------------


def sanitize_url(url: Optional[str]) -> Optional[str]:
    """Path plus query *names*, with sensitive values replaced.

    Applied to everything this tool prints, including `Location` headers, so a
    redirect carrying an authorization code or a session identifier cannot
    reach the terminal or a report by accident.
    """
    if not url:
        return url
    split = urlsplit(url)
    pairs = [
        (key, value if key == "version" and re.fullmatch(r"[0-9.]+", value)
         else REDACTED)
        for key, value in parse_qsl(split.query, keep_blank_values=True)
    ]
    # `safe="<>"` keeps the redaction marker legible: percent-encoding it to
    # `%3Credacted%3E` would still be safe, but a report nobody can read at a
    # glance is a report that gets skimmed.
    query = urlencode(pairs, safe="<>") if pairs else ""
    path = split.path or "/"
    return f"{path}?{query}" if query else path


# --- Safe transport ------------------------------------------------------


class UnsafeRequest(RuntimeError):
    """Raised rather than performing a request that breaks the tool's contract."""


def _is_loopback(host: str) -> bool:
    # Literal addresses avoid a DNS check/connect race and external resolution.
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Redirects are evidence to record, not hops to follow."""

    def redirect_request(self, *_args, **_kwargs):
        return None


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes = field(repr=False)
    url: str

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";")[0].strip()

    @property
    def set_cookie_present(self) -> bool:
        return "set-cookie" in self.headers

    def text(self) -> str:
        return self.body.decode("utf-8", "replace")


def fetch(url: str, method: str = "GET", timeout: int = TIMEOUT) -> Response:
    """The only network call in this module, and it can only be safe.

    Two invariants are enforced here rather than documented elsewhere, because
    a rule that lives only in a docstring is a rule that gets broken by the
    next caller.
    """
    if method not in SAFE_METHODS:
        raise UnsafeRequest(f"{method} is not a safe method; only GET and HEAD")
    split = urlsplit(url)
    if split.scheme not in {"http", "https"} or split.username is not None or split.password is not None:
        raise UnsafeRequest("only credential-free HTTP(S) URLs are accepted")
    if not 0 < timeout <= TIMEOUT:
        raise UnsafeRequest("timeout must be positive and at most five seconds")
    host = split.hostname or ""
    if not _is_loopback(host):
        raise UnsafeRequest("a literal loopback address is required")

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)
    request = urllib.request.Request(url, method=method)
    try:
        raw = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as error:  # 4xx/5xx are evidence
        raw = error
    with raw:
        body = raw.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise UnsafeRequest("response exceeds discovery size limit")
        # Never retain cookie values; only their presence is evidence.
        headers = {
            k.lower(): ("present" if k.lower() == "set-cookie" else v)
            for k, v in raw.headers.items()
            if k.lower() in {"content-type", "location", "set-cookie"}
        }
        if "location" in headers:
            headers["location"] = sanitize_url(headers["location"])
        return Response(raw.status, headers, body, sanitize_url(url))


# --- HTML asset extraction ----------------------------------------------


@dataclass(frozen=True)
class AssetReference:
    path: str  # same-origin: path only. cross-origin: scheme://host/path
    element: str  # the HTML element that referenced it
    same_origin: bool

    def sort_key(self) -> tuple:
        return (not self.same_origin, self.element, self.path)


class _AssetParser(HTMLParser):
    """Collects the URL-bearing attributes that matter for an allow-list.

    Deliberately narrow: `link/@href`, `script/@src`, `img/@src`, `form/@action`
    and `a/@href`. Anything a page pulls from CSS (`url(...)` in a stylesheet,
    `@font-face`) is invisible here, which is precisely why the classifier
    below refuses to promote a prefix to "exact paths are enough" on the
    strength of one HTML render.
    """

    _ATTRS = {
        "link": "href",
        "script": "src",
        "img": "src",
        "form": "action",
        "a": "href",
        "source": "src",
        "use": "href",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        wanted = self._ATTRS.get(tag)
        if wanted is None:
            return
        for name, value in attrs:
            if name == wanted and value:
                self.found.append((tag, value))


def extract_assets(html_text: str, base_url: str) -> list[AssetReference]:
    """Path-level references from one page, normalised and de-duplicated.

    Fragment-only and non-http schemes (`#`, `javascript:`, `mailto:`, `data:`)
    are dropped: none of them is a request that an allow-list could ever see.
    """
    parser = _AssetParser()
    parser.feed(html_text)
    base = urlsplit(base_url)

    references: dict[tuple[str, str], AssetReference] = {}
    for element, raw in parser.found:
        raw = raw.strip()
        if not raw or raw.startswith(("#", "javascript:", "mailto:", "data:", "tel:")):
            continue
        absolute = urljoin(base_url, raw)
        split = urlsplit(absolute)
        if split.scheme not in ("http", "https"):
            continue
        if split.username is not None or split.password is not None:
            continue
        same_origin = (split.scheme, split.netloc) == (base.scheme, base.netloc)
        path = sanitize_url(absolute) if same_origin else f"{split.scheme}://{split.netloc}{split.path}"
        reference = AssetReference(path=path, element=element, same_origin=same_origin)
        references.setdefault((reference.path, reference.element), reference)

    return sorted(references.values(), key=AssetReference.sort_key)


# --- CSS sub-resource extraction ----------------------------------------

# `url(...)` in a stylesheet. The HTML parser above cannot see these, and they
# are where the interesting sub-resources live: an icon font referenced from a
# CSS file is invisible to any allow-list built by reading the page source.
_CSS_URL = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""")


def extract_css_urls(css: str, css_url: str) -> list[str]:
    """Same-origin paths a stylesheet pulls in, resolved against its own URL.

    `data:` URIs are dropped -- they are inline bytes, not requests. Anything
    still carrying an unexpanded template variable is kept as-is rather than
    silently repaired: a `${...}` in shipped CSS is an observation about the
    provider, and hiding it would lose that.
    """
    paths = set()
    base = css_url.split("?")[0]
    for raw in _CSS_URL.findall(css):
        raw = raw.strip()
        if not raw or raw.startswith("data:"):
            continue
        split = urlsplit(urljoin(base, raw))
        origin = urlsplit(css_url)
        if split.scheme not in ("", "http", "https"):
            continue
        if (split.scheme, split.netloc) != (origin.scheme, origin.netloc):
            continue
        paths.add(split.path)
    return sorted(paths)


def top_level_prefix(path: str) -> str:
    """`/fonts/x.woff2` -> `/fonts/`. The unit an nginx prefix rule works in."""
    segments = [segment for segment in path.split("/") if segment]
    return f"/{segments[0]}/" if len(segments) > 1 else path


# --- Prefix classification ----------------------------------------------


def paths_under(prefix: str, references: Iterable[AssetReference]) -> list[str]:
    return sorted(
        {
            reference.path
            for reference in references
            if reference.same_origin and reference.path.split("?")[0].startswith(prefix)
        }
    )


# A dotted version inside a filename: `font-awesome-4.7.0.min.css`,
# `prime-min-1.7.0.js`. Two components are enough; `128` alone is not a
# version, it is a pixel size.
_SEMVER_IN_NAME = re.compile(r"\d+\.\d+(?:\.\d+)*")
# A content hash: a long alphanumeric run mixing letters and digits.
_HASH_IN_NAME = re.compile(r"\b(?=[a-z0-9]*\d)(?=[a-z0-9]*[a-z])[a-z0-9]{8,}\b", re.I)


def looks_versioned(path: str) -> bool:
    """Does this path carry a cache-busting or version-bearing token?

    This is the question that decides whether an exact allow-list survives a
    FusionAuth upgrade or silently breaks the login page, so it must not be
    answered by a loose heuristic. Three signals count, and nothing else:

      * any query string (`?version=1.69.0`) -- cache-busting by definition;
      * a dotted version in a path segment (`4.7.0`, `1.7.0`);
      * a long mixed letter/digit run, i.e. a content hash.

    Explicitly *not* a version: a bare number or a size pair. `favicon-128.png`
    and `apple-icon-114x114.png` describe pixel dimensions and are as stable as
    any other filename. Treating them as versioned would manufacture an
    argument for a wide rule out of nothing, which is the opposite of what this
    tool is for.
    """
    if "?" in path:
        return True
    for segment in path.split("/"):
        if not segment:
            continue
        stem = segment.rsplit(".", 1)[0] if "." in segment else segment
        if _SEMVER_IN_NAME.search(segment):
            return True
        for chunk in re.split(r"[-_.]", stem):
            if _HASH_IN_NAME.fullmatch(chunk):
                return True
    return False


def classify_prefix(
    prefix: str, references: Iterable[AssetReference], *, pages_observed: int
) -> tuple[str, str]:
    """(classification, reason) for one published prefix.

    The `pages_observed` guard is the point of this function. The nginx
    template's three prefixes exist because nobody measured them; replacing
    them with exact paths on the strength of a single page render would repeat
    that mistake in the opposite direction.
    """
    observed = paths_under(prefix, references)
    if not observed:
        return (
            NOT_OBSERVED,
            f"no reference under {prefix} in {pages_observed} observed page(s)",
        )
    versioned = [path for path in observed if looks_versioned(urlsplit(path).path)]
    if versioned:
        return (
            REQUIRED_AS_PREFIX,
            f"generic-page candidate: {len(observed)} path(s), {len(versioned)} filename-versioned "
            f"(e.g. {versioned[0]}); exact paths may change on upgrade; real login unverified",
        )
    if pages_observed < 2:
        return (
            INSUFFICIENT_EVIDENCE,
            f"{len(observed)} path(s) from a single page render; the login and "
            "second-factor pages have not been observed",
        )
    if len(observed) == 1:
        return CAN_REPLACE_WITH_EXACT_PATHS, f"a single stable path: {observed[0]}"
    return CAN_NARROW, f"generic-page candidate: {len(observed)} paths without filename versions; real login unverified"


# --- Object existence, by discrimination rather than inference -----------

# The trap this exists to avoid: FusionAuth answers a *malformed* authorization
# request, an *unknown* client and several other faults with the same 200
# themed error page. Reading that page as "the object does not exist" is an
# inference, not a measurement, and it produced a wrong conclusion once.
#
# What discriminates is finer-grained: the tenant-scoped discovery document
# resolves or does not, and the OAuth error body names a *reason*. Both are
# unauthenticated and read-only.

EXISTS = "EXISTS"
ABSENT = "ABSENT"
INDETERMINATE = "INDETERMINATE"

_ERROR_REASON = re.compile(r'"error_reason"\s*:\s*"([^"]+)"')

# A UUID that is well-formed but chosen to not exist, used as the control.
_CONTROL_UUID = "00000000-0000-0000-0000-000000000000"


def oauth_error_reason(html_body: str) -> Optional[str]:
    """FusionAuth renders the OAuth error object inside the themed page.

    It arrives HTML-escaped -- `&quot;error_reason&quot;` -- so the entities
    must be resolved before matching. Reading the raw markup finds nothing and
    silently degrades every verdict to INDETERMINATE.
    """
    match = _ERROR_REASON.search(html.unescape(html_body))
    if not match:
        return None
    reason = match.group(1)
    return reason if reason in {
        "invalid_client_id", "invalid_redirect_uri", "invalid_tenant_id"
    } else "unrecognized_error_reason"


def probe_tenant(base: str, tenant_id: str, controls: Iterable[str] = ()) -> dict:
    """Does `tenant_id` resolve? Answered against a control group.

    A verdict is only returned when the controls actually behave differently
    from the subject. If a control resolves too, the test discriminates nothing
    and the result is INDETERMINATE rather than a false EXISTS.
    """
    path = "/.well-known/openid-configuration"
    subject = fetch(f"{base}{path}/{tenant_id}").status
    control_statuses = [fetch(f"{base}{path}/{c}").status for c in controls]

    verdict = INDETERMINATE
    if control_statuses and all(status != subject for status in control_statuses):
        verdict = EXISTS if subject == 200 else INDETERMINATE
    return {
        "tenant_id": tenant_id,
        "status": subject,
        "control_statuses": control_statuses,
        "verdict": verdict,
    }


def probe_application(base: str, client_id: str, tenant_id: Optional[str] = None) -> dict:
    """Does `client_id` resolve? Read from the OAuth error *reason*.

    `invalid_client_id` means FusionAuth rejected the client itself. Only
    `invalid_redirect_uri` is accepted as evidence of later validation.
    Unknown reasons remain indeterminate. The redirect URI below
    is deliberately unusable, so this can never complete an authorization.
    """
    query = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": "https://discovery-probe.invalid/cb",
        "scope": "openid",
        "state": "probe",
        "nonce": "probe",
        "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
        "code_challenge_method": "S256",
    }
    if tenant_id:
        query["tenantId"] = tenant_id
    response = fetch(f"{base}/oauth2/authorize?{urlencode(query)}")
    reason = oauth_error_reason(response.text())
    return {
        "client_id": client_id,
        "tenant_id": tenant_id,
        "status": response.status,
        "error_reason": reason,
        "verdict": classify_application_reason(reason),
    }


def classify_application_reason(reason: Optional[str]) -> str:
    if reason == "invalid_client_id":
        return ABSENT
    if reason == "invalid_tenant_id":
        return INDETERMINATE  # the tenant failed first; says nothing about the client
    if reason is None:
        return INDETERMINATE
    return EXISTS if reason == "invalid_redirect_uri" else INDETERMINATE


# --- Report --------------------------------------------------------------


@dataclass
class Discovery:
    base: str
    reachable: bool = False
    metadata: dict[str, str] = field(default_factory=dict)
    pages: list[dict] = field(default_factory=list)
    references: list[AssetReference] = field(default_factory=list)
    stylesheets_followed: list[str] = field(default_factory=list)
    css_sub_resources: list[str] = field(default_factory=list)

    @property
    def pages_observed(self) -> int:
        return len([page for page in self.pages if page.get("is_html")])

    def unpublished_prefixes(self) -> dict[str, list[str]]:
        """Sub-resource prefixes the nginx allow-list does not publish.

        These are CSS references on generic pages, not proof of browser
        requests or of real JUVAl login requirements.
        """
        missing: dict[str, list[str]] = {}
        for path in self.css_sub_resources:
            prefix = top_level_prefix(path)
            if prefix not in PUBLISHED_PREFIXES:
                missing.setdefault(prefix, []).append(path)
        return missing


METADATA_KEYS = (
    "issuer",
    "authorization_endpoint",
    "token_endpoint",
    "userinfo_endpoint",
    "end_session_endpoint",
    "jwks_uri",
    "device_authorization_endpoint",
    "code_challenge_methods_supported",
)


def discover(base: str) -> Discovery:
    result = Discovery(base=base.rstrip("/"))

    try:
        response = fetch(f"{result.base}/.well-known/openid-configuration")
    except (urllib.error.URLError, OSError):
        return result
    if response.status != 200:
        return result
    result.reachable = True

    document = json.loads(response.text())
    for key in METADATA_KEYS:
        value = document.get(key)
        if isinstance(value, str) and value.startswith("http"):
            value = urlsplit(value).path or "/"
        if value is not None:
            result.metadata[key] = value

    # Generic pages only. A request without client_id says nothing about
    # whether the JUVAl application exists. Never submit the forgot form.
    for label, path in (
        ("generic authorization error (missing client_id)", "/oauth2/authorize"),
        ("hosted form page (forgot-password, rendered not submitted)", "/password/forgot"),
    ):
        page = fetch(f"{result.base}{path}")
        is_html = page.content_type == "text/html"
        result.pages.append(
            {
                "label": label,
                "path": path,
                "status": page.status,
                "content_type": page.content_type,
                "bytes": len(page.body),
                "is_html": is_html,
                "set_cookie_present": page.set_cookie_present,
                "location": sanitize_url(page.headers.get("location")),
                "evidence": "OBSERVED_GENERIC_FORM",
            }
        )
        if is_html:
            result.references.extend(extract_assets(page.text(), f"{result.base}{path}"))

    seen: dict[tuple[str, str], AssetReference] = {}
    for reference in result.references:
        seen.setdefault((reference.path, reference.element), reference)
    result.references = sorted(seen.values(), key=AssetReference.sort_key)

    # Follow each same-origin stylesheet one level, for the sub-resources no
    # amount of HTML parsing can reveal. One level only: this is evidence
    # collection, not a crawler.
    sub_resources: set[str] = set()
    for reference in result.references:
        if reference.element != "link" or not reference.same_origin:
            continue
        if not reference.path.split("?")[0].endswith(".css"):
            continue
        sheet = fetch(f"{result.base}{reference.path}")
        if sheet.status == 200:
            sub_resources.update(extract_css_urls(sheet.text(), f"{result.base}{reference.path}"))
            result.stylesheets_followed.append(reference.path)
    result.css_sub_resources = sorted(sub_resources)
    return result



def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://127.0.0.1:9011")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--tenant-id", help="probe whether this tenant id resolves")
    parser.add_argument("--client-id", help="probe whether this client id resolves")
    args = parser.parse_args(argv)

    if args.tenant_id or args.client_id:
        import uuid as _uuid
        if args.tenant_id:
            controls = [_CONTROL_UUID] + [str(_uuid.uuid4()) for _ in range(3)]
            outcome = probe_tenant(args.base, args.tenant_id, controls)
            print(f"tenant  {args.tenant_id}  status={outcome['status']}  "
                  f"controls={outcome['control_statuses']}  -> {outcome['verdict']}")
        if args.client_id:
            outcome = probe_application(args.base, args.client_id, args.tenant_id)
            print(f"client  {args.client_id}  reason={outcome['error_reason']}  "
                  f"-> {outcome['verdict']}")
            control = probe_application(args.base, str(_uuid.uuid4()), args.tenant_id)
            print(f"control {'(random client)':<38} reason={control['error_reason']}  "
                  f"-> {control['verdict']}")
        return 0

    result = discover(args.base)
    if not result.reachable:
        print("BLOCKED  no loopback OIDC discovery document", file=sys.stderr)
        return 2

    classifications = {
        prefix: classify_prefix(
            prefix, result.references, pages_observed=result.pages_observed
        )
        for prefix in PUBLISHED_PREFIXES
    }

    if args.json:
        print(
            json.dumps(
                {
                    "metadata": result.metadata,
                    "pages": result.pages,
                    "references": [
                        {
                            "path": r.path,
                            "element": r.element,
                            "same_origin": r.same_origin,
                        }
                        for r in result.references
                    ],
                    "css_sub_resources": result.css_sub_resources,
                    "unpublished_prefixes": result.unpublished_prefixes(),
                    "prefix_classification": {
                        k: {"classification": v[0], "reason": v[1]}
                        for k, v in classifications.items()
                    },
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    print("--- OIDC metadata (paths only) ---")
    for key in METADATA_KEYS:
        if key in result.metadata:
            print(f"  {key:32} {result.metadata[key]}")
    print()
    print("--- pages observed ---")
    for page in result.pages:
        print(
            f"  GET {page['path']:<22} {page['status']}  {page['content_type']:<10} "
            f"{page['bytes']}B  SET_COOKIE_PRESENT={'YES' if page['set_cookie_present'] else 'NO'}"
        )
        if page["location"]:
            print(f"      Location (sanitised): {page['location']}")
    print()
    print("--- same-origin references ---")
    same = [r for r in result.references if r.same_origin]
    if not same:
        print("  (none)")
    for reference in same:
        print(f"  {reference.element:<7} {reference.path}")
    cross = [r for r in result.references if not r.same_origin]
    if cross:
        print("--- cross-origin references ---")
        for reference in cross:
            print(f"  {reference.element:<7} {reference.path}")
    print()
    print(f"--- sub-resources from CSS ({len(result.stylesheets_followed)} stylesheet(s) followed) ---")
    for path in result.css_sub_resources:
        prefix = top_level_prefix(path)
        mark = "published" if prefix in PUBLISHED_PREFIXES else "NOT PUBLISHED -> 404"
        print(f"  {path:<62} {mark}")
    print()
    print("--- published prefixes ---")
    for prefix, (classification, reason) in classifications.items():
        print(f"  {prefix:<10} {classification:<30} {reason}")
    missing = result.unpublished_prefixes()
    if missing:
        print()
        print("--- prefixes the hosted pages need and the allow-list omits ---")
        for prefix, paths in sorted(missing.items()):
            print(f"  {prefix:<12} {len(paths)} file(s): {', '.join(paths[:3])}"
                  f"{' ...' if len(paths) > 3 else ''}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        sys.exit(main())
    except (UnsafeRequest, urllib.error.URLError, OSError, ValueError):
        # Exceptions can contain request URLs: do not print their messages.
        print("BLOCKED  unsafe request, transport failure or invalid response", file=sys.stderr)
        sys.exit(2)
