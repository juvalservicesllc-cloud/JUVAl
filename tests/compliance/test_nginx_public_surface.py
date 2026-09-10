"""The public identity surface, verified statically and behaviourally.

Two layers, deliberately separated because they carry different weight:

* the static tests read `deploy/fusionauth/nginx-fusionauth-public.conf` and
  pin its shape -- how many rules it has, that the never-publish list is
  absent, that every proxying rule restricts its methods. These always run;
* the behavioural tests start a real nginx on loopback with a disposable echo
  upstream and measure what the file actually does. They need an nginx binary
  and skip without one -- the same shape as the session-store contract tests,
  which skip without a PostgreSQL.

No installation, and no `sudo`, is required to run the second layer:

    cd "$(mktemp -d)" && apt-get download nginx && dpkg-deb -x nginx_*.deb root
    export JUVAL_NGINX_BIN="$PWD/root/usr/sbin/nginx"

That binary is an ordinary file in a scratch directory; deleting the directory
is the whole uninstall. `nginx` on `PATH` works too, and is never started with
a system prefix or a system configuration either way.

Neither layer touches FusionAuth, `/etc/nginx`, or any port other than an
ephemeral loopback one. Nothing here can promote the five rules the template
marks `NOT_VERIFIED`: that annotation is a question about what FusionAuth
1.69.0 serves, and the answer needs a FusionAuth instance, not a proxy. What
these tests do establish is that the proxy dispatches, denies and forwards the
way the file claims -- including the two places where it measurably does not.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

# Same loading convention as test_compliance_check.py: `tools/` is a directory
# of scripts, not an installed package, and only `src` is on the pythonpath.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location(
    "nginx_surface_lab", REPO_ROOT / "tools" / "nginx_surface_lab.py"
)
lab_module = importlib.util.module_from_spec(_spec)
sys.modules["nginx_surface_lab"] = lab_module
_spec.loader.exec_module(lab_module)

DENIED_METHOD = lab_module.DENIED_METHOD
LAB_PUBLIC_HOST = lab_module.LAB_PUBLIC_HOST
MALFORMED = lab_module.MALFORMED
NOT_PUBLISHED = lab_module.NOT_PUBLISHED
PROBES = lab_module.PROBES
PROXIED = lab_module.PROXIED
REDIRECTED = lab_module.REDIRECTED
TEMPLATE = lab_module.TEMPLATE
NginxLab = lab_module.NginxLab
find_nginx = lab_module.find_nginx
measure_bare_prefix_redirect = lab_module.measure_bare_prefix_redirect
measure_denied_response = lab_module.measure_denied_response
measure_forwarding = lab_module.measure_forwarding
measure_missing_host_include = lab_module.measure_missing_host_include
render_lab_config = lab_module.render_lab_config
run_probes = lab_module.run_probes

TEMPLATE_TEXT = TEMPLATE.read_text(encoding="utf-8")

# Paths that must never be published, each with the decision that closes it.
NEVER_PUBLISHED = {
    "/admin": "FusionAuth administrative UI (ADR-035 Condition 2)",
    "/api": "FusionAuth REST API",
    "/account": "self-service portal, answers 200 on Community",
    "/password": "forgot/change (ADR-035 Condition 2)",
}


# --- Static: the shape of the file --------------------------------------


def _locations() -> list[str]:
    return re.findall(r"^\s*location\s+(.+?)\s*\{", TEMPLATE_TEXT, re.MULTILINE)


def _location_blocks() -> list[tuple[str, str]]:
    """(spec, body) for each location, brace-matched rather than split.

    `limit_except { ... }` nests, so anything that stops at the first closing
    brace reads the wrong body -- which is exactly the mistake this helper
    exists to avoid.
    """
    blocks = []
    for match in re.finditer(r"^\s*location\s+(.+?)\s*\{", TEMPLATE_TEXT, re.MULTILINE):
        depth, index = 1, match.end()
        while depth and index < len(TEMPLATE_TEXT):
            depth += {"{": 1, "}": -1}.get(TEMPLATE_TEXT[index], 0)
            index += 1
        blocks.append((match.group(1), TEMPLATE_TEXT[match.end() : index - 1]))
    return blocks


def test_rule_inventory_is_exactly_seven_exact_three_prefix_and_a_catch_all():
    # PROJECT_STATUS.md's 2026-09-10 correction: the file has ten publishing
    # rules, not the "five exact routes" an earlier text claimed. Pinning the
    # count here means the next person to widen the surface has to change a
    # test, which is the point -- every addition is a deliberate act.
    locations = _locations()
    exact = [loc for loc in locations if loc.startswith("= ")]
    prefix = [loc for loc in locations if loc.startswith("^~ ")]
    catch_all = [loc for loc in locations if loc == "/"]

    assert len(exact) == 7, exact
    assert len(prefix) == 3, prefix
    assert len(catch_all) == 1
    assert len(locations) == 11


def test_catch_all_returns_404_and_never_proxies():
    body = dict(_location_blocks())["/"]
    assert "return 404;" in body
    assert "proxy_pass" not in body


@pytest.mark.parametrize("path,reason", sorted(NEVER_PUBLISHED.items()))
def test_never_published_paths_have_no_location(path: str, reason: str):
    assert not any(loc.split()[-1].startswith(path) for loc in _locations()), reason


def test_every_proxying_rule_restricts_its_methods():
    # An allow-listed path that accepts any verb is only half an allow-list.
    proxying = [(spec, body) for spec, body in _location_blocks() if "proxy_pass" in body]
    assert len(proxying) == 10
    for spec, body in proxying:
        assert "limit_except" in body, spec
        assert "deny all;" in body, spec


def test_upstream_is_the_loopback_fusionauth_port_only():
    # 9012 is FusionAuth 1.69.0's factory second listener. Publishing it would
    # widen the surface silently, so only 9011 may appear.
    assert re.findall(r"proxy_pass\s+(\S+);", TEMPLATE_TEXT) == [
        "http://127.0.0.1:9011"
    ] * 10


def test_listener_is_loopback_only():
    assert re.findall(r"^\s*listen\s+(.+);", TEMPLATE_TEXT, re.MULTILINE) == [
        "127.0.0.1:8080"
    ]


# --- Static: the lab may not test something other than the shipped file --


def test_lab_rendering_preserves_every_routing_and_header_rule():
    rendered = render_lab_config(TEMPLATE_TEXT, 18080, 17011)
    for directive in ("location", "limit_except", "return", "proxy_set_header"):
        assert re.findall(rf"^\s*{directive}\b.*$", rendered, re.MULTILINE) == (
            re.findall(rf"^\s*{directive}\b.*$", TEMPLATE_TEXT, re.MULTILINE)
        )
    # Every upstream is redirected at the mock: the lab must be incapable of
    # reaching FusionAuth even if one were running on this host.
    assert re.findall(r"proxy_pass\s+(\S+);", rendered) == [
        "http://127.0.0.1:17011"
    ] * 10
    assert re.findall(r"^\s*listen\s+(.+);", rendered, re.MULTILINE) == [
        "127.0.0.1:18080"
    ]
    assert LAB_PUBLIC_HOST in rendered


def test_lab_rendering_refuses_a_template_it_no_longer_recognises():
    with pytest.raises(ValueError):
        render_lab_config("server { listen 80; }", 18080, 19011)


# --- Behavioural ---------------------------------------------------------

nginx_required = pytest.mark.skipif(
    find_nginx() is None,
    reason="no nginx binary; set JUVAL_NGINX_BIN (see this module's docstring)",
)


@pytest.fixture(scope="module")
def lab():
    binary = find_nginx()
    if binary is None:  # pragma: no cover - guarded by the marker
        pytest.skip("no nginx binary")
    instance = NginxLab(binary, TEMPLATE_TEXT)
    instance.start()
    try:
        yield instance
    finally:
        instance.close()


@pytest.fixture(scope="module")
def probe_results(lab):
    return run_probes(lab)


@nginx_required
def test_rendered_config_passes_nginx_config_test(lab):
    result = lab.config_test()
    assert result.returncode == 0, result.stderr


@nginx_required
@pytest.mark.parametrize(
    "index", range(len(PROBES)), ids=[f"{p.method} {p.target}" for p in PROBES]
)
def test_probe_behaves_as_recorded(probe_results, index: int):
    result = probe_results[index]
    assert result.status == result.probe.expected_status, (
        f"{result.probe.method} {result.probe.target}: expected "
        f"{result.probe.expected_status} ({result.probe.expect}), got {result.status}"
    )
    assert result.reached_upstream is (result.probe.expect == PROXIED), (
        f"{result.probe.method} {result.probe.target}: upstream contact was "
        f"{result.reached_upstream}, expected {result.probe.expect == PROXIED}"
    )


@nginx_required
def test_no_denied_request_ever_reached_the_upstream(probe_results):
    # The single property the whole allow-list exists to provide.
    denied = [
        r
        for r in probe_results
        if r.probe.expect in {DENIED_METHOD, NOT_PUBLISHED, MALFORMED, REDIRECTED}
    ]
    assert denied, "the probe set no longer exercises any denial"
    assert not [r for r in denied if r.reached_upstream]


@nginx_required
def test_authorization_query_string_survives_byte_for_byte(lab):
    forwarding = measure_forwarding(lab)
    assert forwarding["target"].startswith("/oauth2/authorize?")
    # PKCE and CSRF both break if any of these is dropped or re-encoded.
    for fragment in (
        "response_type=code",
        "redirect_uri=https%3A%2F%2Fapp.example%2Fcb",
        "scope=openid+profile",
        "state=abc.123-_~",
        "code_challenge_method=S256",
    ):
        assert fragment in forwarding["target"], fragment


@nginx_required
def test_forwarded_headers_are_set_by_the_proxy_not_by_the_client(lab):
    # measure_forwarding sends hostile values for all five. FusionAuth builds
    # its issuer from these, so a client that could set them could move the
    # issuer -- the discovery document would then disagree with what
    # interfaces/api/auth.py validates.
    forwarding = measure_forwarding(lab)
    assert forwarding["host"] == LAB_PUBLIC_HOST
    assert forwarding["x-forwarded-host"] == LAB_PUBLIC_HOST
    assert forwarding["x-forwarded-proto"] == "https"
    assert forwarding["x-forwarded-port"] == "443"
    assert "attacker.example" not in str(forwarding)


@nginx_required
def test_x_forwarded_for_appends_rather_than_replaces(lab):
    # $proxy_add_x_forwarded_for keeps the client-claimed chain and appends the
    # peer. The appended value is the only trustworthy element; the rest is
    # evidence, not identity.
    forwarding = measure_forwarding(lab)
    assert forwarding["x-forwarded-for"] == "203.0.113.9, 127.0.0.1"


@nginx_required
@pytest.mark.parametrize("prefix", ["/css", "/js", "/images"])
@pytest.mark.parametrize("host", ["attacker.example", "attacker.example:8443", LAB_PUBLIC_HOST])
def test_bare_asset_prefix_redirect_is_relative_and_preserves_query(lab, prefix, host):
    before = len(lab.upstream.seen)
    status, headers, _body = lab.request("GET", prefix + "?version=1.69.0&x=a%2Fb",
                                        {"Host": host, "X-Forwarded-Proto": "http"})
    assert status == 301
    assert headers["location"] == prefix + "/?version=1.69.0&x=a%2Fb"
    assert len(lab.upstream.seen) == before


@nginx_required
def test_traversal_above_the_root_is_rejected_before_routing(lab):
    """Finding N-2: fail-closed, and closed earlier than expected."""
    for target in ("/../admin", "/%2e%2e/admin", "/js/../../api/user"):
        status, _headers, _body = lab.request("GET", target)
        assert status == 400, target


@nginx_required
def test_template_cannot_be_enabled_without_the_host_include(lab):
    # If nginx tolerated the missing include, $juval_public_host would expand
    # empty and FusionAuth would advertise an issuer with a blank host.
    measured = measure_missing_host_include(lab.binary, TEMPLATE_TEXT)
    assert measured["config_test_rejected"] is True
    assert measured["names_the_variable"] is True


@nginx_required
@pytest.mark.parametrize("target,status", [("/admin", 404), ("/css", 301), ("/../admin", 400)])
def test_nginx_generated_responses_do_not_disclose_version(lab, target, status):
    result, headers, body = lab.request("GET", target)
    assert result == status
    assert headers["server"] == "nginx"
    assert b"nginx/" not in body


def test_redirect_and_version_policy_are_pinned_in_the_template():
    assert re.search(r"^\s*absolute_redirect off;", TEMPLATE_TEXT, re.MULTILINE)
    assert re.search(r"^\s*server_tokens off;", TEMPLATE_TEXT, re.MULTILINE)
