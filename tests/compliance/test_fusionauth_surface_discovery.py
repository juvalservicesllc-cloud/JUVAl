"""Unit tests for the read-only FusionAuth surface discovery tool.

No test here touches the network. The tool's value is its parsing and its
refusals, and both are pure functions: the sanitiser that keeps a redirect's
secrets out of a report, the two extractors that decide which paths an
allow-list must cover, and the classifier that must say
`INSUFFICIENT_EVIDENCE` rather than invent a verdict from one page render.

`fetch()` is tested only for the two requests it must refuse. Everything it
would accept needs a live instance, and a test that needs FusionAuth running is
a test that fails for the wrong reason.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location(
    "fusionauth_surface_discovery", REPO_ROOT / "tools" / "fusionauth_surface_discovery.py"
)
discovery = importlib.util.module_from_spec(_spec)
sys.modules["fusionauth_surface_discovery"] = discovery
_spec.loader.exec_module(discovery)

AssetReference = discovery.AssetReference
BASE = "http://127.0.0.1:9011"


def _ref(path: str, element: str = "link", same_origin: bool = True) -> AssetReference:
    return AssetReference(path=path, element=element, same_origin=same_origin)


# --- the sanitiser: secrets must not reach a report ----------------------


@pytest.mark.parametrize("param", sorted(discovery.SENSITIVE_PARAMS))
def test_every_sensitive_parameter_value_is_redacted(param: str):
    sanitized = discovery.sanitize_url(f"{BASE}/oauth2/authorize?{param}=s3cr3t-value")
    assert "s3cr3t-value" not in sanitized
    assert param in sanitized, "the parameter *name* is the evidence and must survive"
    assert discovery.REDACTED in sanitized


def test_query_values_are_redacted_by_default():
    sanitized = discovery.sanitize_url(f"{BASE}/oauth2/authorize?response_type=code&scope=openid")
    assert sanitized == "/oauth2/authorize?response_type=<redacted>&scope=<redacted>"


def test_sanitiser_drops_scheme_and_host():
    assert discovery.sanitize_url(f"{BASE}/a/b").startswith("/a/b")
    assert "127.0.0.1" not in discovery.sanitize_url(f"{BASE}/a/b")


@pytest.mark.parametrize("value", [None, ""])
def test_sanitiser_passes_through_empty(value):
    assert discovery.sanitize_url(value) == value


def test_sanitiser_handles_a_bare_path_with_no_query():
    assert discovery.sanitize_url("/oauth2/logout") == "/oauth2/logout"


# --- fetch(): the refusals are the contract ------------------------------


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def test_fetch_refuses_every_unsafe_method(method: str):
    # Discovery must be incapable of changing FusionAuth state. This is the
    # mechanism that makes "read-only" a property rather than a promise.
    with pytest.raises(discovery.UnsafeRequest):
        discovery.fetch(f"{BASE}/api/user", method=method)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/.well-known/openid-configuration",
        "https://8.8.8.8/oauth2/authorize",
        "http://idp.example.org/",
    ],
)
def test_fetch_refuses_any_non_loopback_host(url: str):
    with pytest.raises(discovery.UnsafeRequest):
        discovery.fetch(url)


# --- HTML asset extraction ----------------------------------------------

HTML = """
<html><head>
  <link rel="stylesheet" href="/css/entrypoints/fusionauth-hosted.css?version=1.69.0">
  <link rel="icon" href="/images/favicon-32x32.png">
  <script src="/js/Util.js?version=1.69.0"></script>
</head><body>
  <form action="/password/forgot" method="POST"><input name="email"></form>
  <img src="/images/footer-logo.svg">
  <a href="https://fusionauth.io">powered by</a>
  <a href="#skip">skip</a>
  <a href="javascript:void(0)">noop</a>
  <a href="mailto:someone@example.com">mail</a>
  <img src="data:image/gif;base64,R0lGOD">
  <script src="relative/thing.js"></script>
</body></html>
"""


def test_extract_assets_finds_each_url_bearing_element():
    found = {(r.element, r.path) for r in discovery.extract_assets(HTML, f"{BASE}/oauth2/authorize")}
    assert ("link", "/css/entrypoints/fusionauth-hosted.css?version=1.69.0") in found
    assert ("link", "/images/favicon-32x32.png") in found
    assert ("script", "/js/Util.js?version=1.69.0") in found
    assert ("form", "/password/forgot") in found
    assert ("img", "/images/footer-logo.svg") in found


def test_extract_assets_marks_cross_origin_and_keeps_its_host():
    cross = [r for r in discovery.extract_assets(HTML, f"{BASE}/x") if not r.same_origin]
    assert [r.path for r in cross] == ["https://fusionauth.io"]


@pytest.mark.parametrize("noise", ["#skip", "javascript:void(0)", "mailto:", "data:image"])
def test_extract_assets_drops_what_can_never_be_a_request(noise: str):
    # None of these is a URL an allow-list could ever see, so counting them
    # would inflate the evidence for a wider rule.
    paths = [r.path for r in discovery.extract_assets(HTML, f"{BASE}/x")]
    assert not any(noise in path for path in paths)


def test_extract_assets_resolves_relative_references_against_the_page():
    paths = [r.path for r in discovery.extract_assets(HTML, f"{BASE}/oauth2/authorize")]
    assert "/oauth2/relative/thing.js" in paths


def test_extract_assets_deduplicates():
    doubled = HTML + HTML
    once = discovery.extract_assets(HTML, f"{BASE}/x")
    twice = discovery.extract_assets(doubled, f"{BASE}/x")
    assert [r.path for r in once] == [r.path for r in twice]


def test_extract_assets_sanitises_sensitive_query_values_in_links():
    html = '<a href="/oauth2/authorize?state=abc123&client_id=deadbeef">back</a>'
    path = discovery.extract_assets(html, f"{BASE}/password/forgot")[0].path
    assert "abc123" not in path and "deadbeef" not in path
    assert "state" in path and "client_id" in path


# --- CSS sub-resources: what HTML parsing cannot see ---------------------

CSS = """
@font-face { src: url('../fonts/fontawesome-webfont.woff2') format('woff2'),
                  url("../fonts/fontawesome-webfont.ttf") format('truetype'); }
.fp { background: url(/assets/icons/fingerprint-overlay.svg); }
.inline { background: url(data:image/svg+xml;base64,PHN2Zz4=); }
"""


def test_extract_css_urls_resolves_relative_to_the_stylesheet():
    # The font files live a directory *above* the stylesheet. Resolving these
    # against the page instead of the stylesheet would miss them entirely --
    # which is exactly how /fonts/ stayed absent from the allow-list.
    found = discovery.extract_css_urls(CSS, "/css/entrypoints/fusionauth-hosted.css?version=1.69.0")
    assert "/css/fonts/fontawesome-webfont.woff2" in found
    assert "/assets/icons/fingerprint-overlay.svg" in found


def test_extract_css_urls_drops_inline_data_uris():
    assert not [p for p in discovery.extract_css_urls(CSS, "/css/x.css") if p.startswith("data:")]


def test_extract_css_urls_handles_all_three_quoting_styles():
    css = "a{background:url(a.png)}b{background:url('b.png')}c{background:url(\"c.png\")}"
    found = discovery.extract_css_urls(css, "/css/x.css")
    assert found == ["/css/a.png", "/css/b.png", "/css/c.png"]


def test_extract_css_urls_keeps_an_unexpanded_template_variable_visible():
    # FusionAuth 1.69.0 ships a stylesheet containing a literal
    # `${request.contextPath}`. Silently repairing it would lose an
    # observation about the provider.
    css = "a{background:url(${request.contextPath}/assets/x.svg)}"
    assert discovery.extract_css_urls(css, "/css/e/x.css") == [
        "/css/e/${request.contextPath}/assets/x.svg"
    ]


# --- top-level prefix ----------------------------------------------------


@pytest.mark.parametrize(
    "path,expected",
    [
        ("/fonts/fontawesome-webfont.woff2", "/fonts/"),
        ("/css/entrypoints/fusionauth-hosted.css", "/css/"),
        ("/assets/icons/fingerprint-overlay.svg", "/assets/"),
        ("/favicon.ico", "/favicon.ico"),
    ],
)
def test_top_level_prefix(path: str, expected: str):
    assert discovery.top_level_prefix(path) == expected


# --- versioned-vs-stable: the distinction the recommendation rests on ----


@pytest.mark.parametrize(
    "path",
    [
        "/js/Util.js?version=1.69.0",
        "/css/entrypoints/fusionauth-hosted.css?version=1.69.0",
        "/css/font-awesome-4.7.0.min.css",
        "/js/prime-min-1.7.0.js",
        "/js/app.a8f3c9d21b.js",
    ],
)
def test_version_bearing_paths_are_detected(path: str):
    assert discovery.looks_versioned(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "/images/favicon-128.png",
        "/images/favicon-16x16.png",
        "/images/apple-icon-114x114.png",
        "/images/footer-logo.svg",
        "/images/manifest.json",
    ],
)
def test_pixel_sizes_are_not_mistaken_for_versions(path: str):
    # This is the whole reason the heuristic is tested. A size token read as a
    # version turns /images/ into REQUIRED_AS_PREFIX and manufactures an
    # argument for the widest rule out of nothing.
    assert discovery.looks_versioned(path) is False


# --- prefix classification ----------------------------------------------


def test_prefix_with_versioned_assets_must_stay_a_prefix():
    classification, reason = discovery.classify_prefix(
        "/js/",
        [_ref("/js/Util.js?version=1.69.0", "script"), _ref("/js/prime-min-1.7.0.js", "script")],
        pages_observed=2,
    )
    assert classification == discovery.REQUIRED_AS_PREFIX
    assert "upgrade" in reason


def test_a_single_page_render_is_never_enough_to_narrow():
    # The guard against repeating the original mistake in the other direction.
    classification, _ = discovery.classify_prefix(
        "/images/", [_ref("/images/a.png"), _ref("/images/b.png")], pages_observed=1
    )
    assert classification == discovery.INSUFFICIENT_EVIDENCE


def test_stable_paths_across_several_pages_can_narrow():
    classification, _ = discovery.classify_prefix(
        "/images/", [_ref("/images/a.png"), _ref("/images/b.png")], pages_observed=2
    )
    assert classification == discovery.CAN_NARROW


def test_a_single_stable_path_can_become_an_exact_rule():
    classification, _ = discovery.classify_prefix(
        "/images/", [_ref("/images/only.svg")], pages_observed=3
    )
    assert classification == discovery.CAN_REPLACE_WITH_EXACT_PATHS


def test_an_unreferenced_prefix_is_reported_as_not_observed():
    classification, _ = discovery.classify_prefix("/images/", [_ref("/css/a.css")], pages_observed=2)
    assert classification == discovery.NOT_OBSERVED


def test_cross_origin_references_never_count_towards_a_local_prefix():
    classification, _ = discovery.classify_prefix(
        "/images/",
        [_ref("https://cdn.example/images/a.png", "img", same_origin=False)],
        pages_observed=2,
    )
    assert classification == discovery.NOT_OBSERVED


# --- the missing-prefix report ------------------------------------------


def test_unpublished_prefixes_reports_exactly_what_the_allow_list_would_404():
    result = discovery.Discovery(base=BASE)
    result.css_sub_resources = [
        "/assets/icons/fingerprint-overlay.svg",
        "/css/inside-a-published-prefix.svg",
        "/fonts/fontawesome-webfont.woff2",
        "/fonts/fontawesome-webfont.ttf",
    ]
    missing = result.unpublished_prefixes()
    assert sorted(missing) == ["/assets/", "/fonts/"]
    assert len(missing["/fonts/"]) == 2
    assert "/css/" not in missing, "a published prefix is not a gap"


# --- object existence: the inference trap, closed by discrimination ------
#
# A previous pass concluded "no tenant/application exists" from a generic 200
# error page returned for a placeholder client id. These tests pin the logic
# that makes that conclusion impossible to reach by accident.

ERROR_PAGE = """
<html><head><title>Error</title></head><body>
  <pre>{
  &quot;error&quot; : &quot;invalid_client&quot;,
  &quot;error_description&quot; : &quot;client_id: 913c3a17 is not valid.&quot;,
  &quot;error_reason&quot; : &quot;invalid_client_id&quot;
}</pre>
</body></html>
"""

REDIRECT_ERROR_PAGE = ERROR_PAGE.replace("invalid_client_id", "invalid_redirect_uri")


def test_oauth_error_reason_decodes_html_entities():
    # FusionAuth escapes the JSON into the page. Matching the raw markup finds
    # nothing and silently degrades every verdict to INDETERMINATE -- which is
    # exactly what happened before this was fixed.
    assert discovery.oauth_error_reason(ERROR_PAGE) == "invalid_client_id"
    assert discovery.oauth_error_reason(REDIRECT_ERROR_PAGE) == "invalid_redirect_uri"


def test_oauth_error_reason_is_none_when_absent():
    assert discovery.oauth_error_reason("<html><body>no error block</body></html>") is None


@pytest.mark.parametrize(
    "reason,verdict",
    [
        ("invalid_client_id", discovery.ABSENT),
        ("invalid_redirect_uri", discovery.EXISTS),
        ("invalid_request", discovery.INDETERMINATE),
        ("invalid_tenant_id", discovery.INDETERMINATE),
        (None, discovery.INDETERMINATE),
    ],
)
def test_application_verdict_follows_the_error_reason(reason, verdict):
    # The whole inference: reaching redirect-URI validation proves the client
    # was accepted, because an unknown client fails earlier. A tenant failure
    # says nothing either way and must not be read as absence.
    assert discovery.classify_application_reason(reason) == verdict


def test_a_missing_error_block_is_never_read_as_absence():
    # The precise mistake being prevented: a generic page with no error reason
    # must yield INDETERMINATE, never ABSENT.
    assert discovery.classify_application_reason(None) != discovery.ABSENT


def test_tenant_verdict_requires_controls_to_actually_discriminate(monkeypatch):
    # If the control group behaves like the subject, the probe proves nothing.
    # Returning EXISTS there would be the original error in a new costume.
    statuses = iter([200, 200, 200])
    monkeypatch.setattr(
        discovery, "fetch",
        lambda url, **kw: discovery.Response(next(statuses), {}, b"", url),
    )
    outcome = discovery.probe_tenant(BASE, "subject", controls=["c1", "c2"])
    assert outcome["verdict"] == discovery.INDETERMINATE


def test_tenant_verdict_is_exists_when_controls_differ(monkeypatch):
    statuses = iter([200, 500, 500])
    monkeypatch.setattr(
        discovery, "fetch",
        lambda url, **kw: discovery.Response(next(statuses), {}, b"", url),
    )
    outcome = discovery.probe_tenant(BASE, "subject", controls=["c1", "c2"])
    assert outcome["verdict"] == discovery.EXISTS
    assert outcome["control_statuses"] == [500, 500]


def test_tenant_failure_is_indeterminate_even_when_controls_differ(monkeypatch):
    statuses = iter([500, 200, 200])
    monkeypatch.setattr(
        discovery, "fetch",
        lambda url, **kw: discovery.Response(next(statuses), {}, b"", url),
    )
    assert discovery.probe_tenant(BASE, "s", controls=["c1", "c2"])["verdict"] == discovery.INDETERMINATE


def test_tenant_probe_without_controls_is_indeterminate(monkeypatch):
    monkeypatch.setattr(
        discovery, "fetch", lambda url, **kw: discovery.Response(200, {}, b"", url)
    )
    assert discovery.probe_tenant(BASE, "s")["verdict"] == discovery.INDETERMINATE


def test_application_probe_uses_an_unusable_redirect_uri(monkeypatch):
    # The probe must be incapable of completing an authorization even against a
    # correctly configured application.
    seen = {}

    def _capture(url, **_kw):
        seen["url"] = url
        return discovery.Response(200, {}, ERROR_PAGE.encode(), url)

    monkeypatch.setattr(discovery, "fetch", _capture)
    discovery.probe_application(BASE, "some-client")
    assert "discovery-probe.invalid" in seen["url"]
    assert "response_type=code" in seen["url"]
    assert "code_challenge_method=S256" in seen["url"]


@pytest.mark.parametrize('query', [
    'STATE=private', 'unknown=private',
    'redirect_uri=http%3A%2F%2Flocalhost%2Fcb%3Fcode%3Dprivate',
    'version=private',
])
def test_unknown_case_variant_and_nested_query_secrets_are_redacted(query):
    assert 'private' not in discovery.sanitize_url('/x?' + query)


@pytest.mark.parametrize('url', [
    'ftp://127.0.0.1/x', 'http://user:private@127.0.0.1/x',
    'http://localhost/x', 'http://127.0.0.1.example.com/x',
])
def test_transport_rejects_credentials_schemes_and_dns_names(url):
    with pytest.raises(discovery.UnsafeRequest):
        discovery.fetch(url)


@pytest.mark.parametrize('timeout', [0, -1, 6])
def test_transport_requires_bounded_timeout(timeout):
    with pytest.raises(discovery.UnsafeRequest):
        discovery.fetch(BASE, timeout=timeout)


def test_fetch_disables_proxies_closes_response_and_discards_cookie_values(monkeypatch):
    from io import BytesIO
    raw = BytesIO(b'<html></html>')
    raw.status = 200
    raw.headers = {'Set-Cookie': 'private-cookie', 'Location': '/cb?code=private-code'}
    captured = {}

    class Opener:
        def open(self, request, timeout):
            captured['method'] = request.method
            captured['timeout'] = timeout
            return raw

    def build(*handlers):
        captured['handlers'] = handlers
        return Opener()

    monkeypatch.setattr(discovery.urllib.request, 'build_opener', build)
    result = discovery.fetch(BASE + '/x?state=private-state')
    assert captured['handlers'][0].proxies == {}
    assert captured['handlers'][1] is discovery._NoRedirect
    assert captured['method'] == 'GET' and captured['timeout'] == 5
    assert raw.closed
    assert result.set_cookie_present
    assert 'private' not in repr(result)


def test_transport_rejects_oversized_response_and_closes_it(monkeypatch):
    from io import BytesIO
    raw = BytesIO(b'12345')
    raw.status = 200
    raw.headers = {}
    class Opener:
        def open(self, *args, **kwargs):
            return raw
    monkeypatch.setattr(discovery, 'MAX_RESPONSE_BYTES', 4)
    monkeypatch.setattr(discovery.urllib.request, 'build_opener', lambda *args: Opener())
    with pytest.raises(discovery.UnsafeRequest):
        discovery.fetch(BASE)
    assert raw.closed


def test_css_cross_origin_resources_are_not_local_paths():
    css = 'a{src:url(https://elsewhere.example/fonts/x)} b{src:url(/fonts/local)}'
    assert discovery.extract_css_urls(css, BASE + '/css/x.css') == ['/fonts/local']


def test_html_scheme_change_is_cross_origin_and_userinfo_is_discarded():
    refs = discovery.extract_assets(
        '<img src="https://127.0.0.1:9011/x"><img src="http://u:private@elsewhere.example/x">', BASE)
    assert len(refs) == 1 and not refs[0].same_origin
    assert 'private' not in repr(refs)


@pytest.mark.parametrize('reason', ['server_error', 'invalid_request', 'new_provider_error'])
def test_unrecognized_oauth_reason_never_proves_existence(reason):
    assert discovery.classify_application_reason(reason) == discovery.INDETERMINATE


def test_generic_discovery_does_not_probe_logout_or_label_missing_application(monkeypatch):
    seen = []
    def fetch(url, **kwargs):
        seen.append(url)
        if '.well-known' in url:
            return discovery.Response(200, {}, b'{}', url)
        return discovery.Response(200, {'content-type': 'text/html'}, b'<title>private</title>', url)
    monkeypatch.setattr(discovery, 'fetch', fetch)
    result = discovery.discover(BASE)
    assert not any('/oauth2/logout' in url for url in seen)
    assert all(p['evidence'] == 'OBSERVED_GENERIC_FORM' for p in result.pages)
    assert 'private' not in repr(result)
    assert 'no application configured' not in repr(result)


def test_query_only_version_does_not_require_prefix_for_nginx_matching():
    classification, _ = discovery.classify_prefix(
        '/js/', [_ref('/js/Util.js?version=1.69.0')], pages_observed=2)
    assert classification != discovery.REQUIRED_AS_PREFIX


def test_arbitrary_provider_error_text_is_not_reported():
    reason = discovery.oauth_error_reason('{"error_reason":"private-provider-value"}')
    assert reason == 'unrecognized_error_reason'
    assert discovery.classify_application_reason(reason) == discovery.INDETERMINATE
