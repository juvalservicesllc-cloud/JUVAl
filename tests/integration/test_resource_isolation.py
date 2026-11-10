"""SEC-01D / ADR-056: per-resource authorization between organizations.

Synthetic identities, all under the test issuer:

- `user-a1` (operator) and `user-a2` (viewer) are members of organization A;
- `user-b` (operator) is a member of organization B;
- `user-none` is authenticated but belongs to no organization.

What must hold (owner decisions OD-1..OD-7, 2026-11-10):

- B never reaches anything of A -- runs, records, analytics, financial data,
  exports, downloads, batches -- and listings and counters never include it;
- a foreign resource answers exactly like a missing one (404, same body);
- members of the same organization share its runs, subject to RBAC (OD-2),
  and the creator is recorded for audit;
- an authenticated identity with no membership gets no data at all (403);
- history without an owner is visible to nobody (OD-3);
- no route skips the check: route coverage is read from the application.

Until 2026-11-10 the isolation half of this file was `xfail(strict=True)`
(measured: every authenticated reader saw every run).
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from juval.application.tenancy import OutOfScopeError, Ownership, TenantScope
from juval.domain.execution_run import ExecutionRun, ExecutionStatus
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore
from juval.interfaces.api import auth, service
from juval.interfaces.api.main import app, tenant_access

from .test_api_auth import AUDIENCE, ISSUER, bearer, keypair, make_token  # noqa: F401 (fixture)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_sourcing_TEST_DATA.xlsx"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
THRESHOLDS = json.dumps(
    {"target_profit": "5", "target_roi": "0.3", "minimum_estimated_monthly_sales": 0, "maximum_risk_severity": "LOW"}
)
FEES = json.dumps({"referral_fee": "3", "referral_fee_rate": "0.15", "fulfillment_fee": "2"})
UNKNOWN_RUN = "00000000-0000-4000-8000-000000000000"
ORG_A = "aaaaaaaa-0000-4000-8000-00000000000a"
ORG_B = "bbbbbbbb-0000-4000-8000-00000000000b"
NOW = datetime(2026, 11, 10, tzinfo=timezone.utc)
COUNTS = dict(records_total=0, records_processed=0, records_successful=0, records_with_errors=0, warnings=0)

# Run-scoped routes. `{run}` and `{ref}` are filled in.
RUN_READS = (
    "/api/v1/runs/{run}",
    "/api/v1/runs/{run}/records",
    "/api/v1/runs/{run}/records/{ref}",
    "/api/v1/runs/{run}/analytics",
    "/api/v1/runs/{run}/financial",
    "/api/v1/runs/{run}/records/{ref}/financial",
)
RUN_EXPORTS = ("/api/v1/runs/{run}/records/export", "/api/v1/runs/{run}/download")
DATA_ROUTES = sorted(
    (method, route.path)
    for route in app.routes
    if getattr(route, "path", "").startswith("/api/v1/") and not route.path.startswith("/api/v1/auth")
    for method in route.methods
)


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A disposable SQLite store with organizations A and B and their members."""
    monkeypatch.setenv("JUVAL_RUN_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("JUVAL_EXECUTION_DB_PATH", str(tmp_path / "runs.db"))
    monkeypatch.delenv("JUVAL_EXECUTION_STORE", raising=False)
    monkeypatch.delenv("JUVAL_MAX_UPLOAD_BYTES", raising=False)
    store = SqliteExecutionRunStore(tmp_path / "runs.db")
    store.create_organization(ORG_A, "Synthetic customer A", "test-operator", NOW)
    store.create_organization(ORG_B, "Synthetic customer B", "test-operator", NOW)
    for org, subject in ((ORG_A, "user-a1"), (ORG_A, "user-a2"), (ORG_B, "user-b")):
        store.add_membership(org, ISSUER, subject, "test-operator", NOW)
    return store


@pytest.fixture
def api(db, keypair):  # noqa: F811
    _, public_key = keypair
    verifier = auth.TokenVerifier(issuer=ISSUER, audience=AUDIENCE, key_resolver=lambda token: public_key)
    auth.uninstall(app)
    auth.install(app, auth.AuthSettings(mode="oidc", verifier=verifier))
    yield TestClient(app, raise_server_exceptions=False)
    auth.uninstall(app)


@pytest.fixture
def as_user(keypair):  # noqa: F811
    def headers(subject, role):
        return bearer(make_token(keypair, subject=subject, roles=(role,)))

    return headers


def upload(api, headers, name="a.xlsx"):
    response = api.post(
        "/api/v1/runs",
        headers=headers,
        files={"file": (name, FIXTURE.read_bytes(), XLSX)},
        data={"thresholds": THRESHOLDS, "fees": FEES, "persist": "true"},
    )
    assert response.status_code == 200, response.text
    return response.json()["execution_id"]


@pytest.fixture
def a_run(api, as_user):
    """A persisted run created by user-a1, plus one of its record refs."""
    run = upload(api, as_user("user-a1", "operator"))
    records = api.get(f"/api/v1/runs/{run}/records", headers=as_user("user-a1", "viewer")).json()["records"]
    return run, records[0]["record_ref"]


@pytest.fixture
def a_batch(api, as_user):
    response = api.post(
        "/api/v1/batches",
        headers=as_user("user-a1", "operator"),
        files=[("files", ("a.xlsx", FIXTURE.read_bytes(), XLSX))],
        data={"thresholds": THRESHOLDS, "fees": FEES, "persist": "true"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return body["batch_id"], body["files"][0]["execution_id"]


def fill(path, run, ref="no-such-ref"):
    return path.format(run=run, ref=ref)


def same_as_absent(api, headers, path, run, ref):
    """The foreign response, compared with a missing run on the same route."""
    foreign = api.get(fill(path, run, ref), headers=headers)
    absent = api.get(fill(path, UNKNOWN_RUN, ref), headers=headers)
    assert absent.status_code == 404, path
    assert (foreign.status_code, foreign.content) == (absent.status_code, absent.content), path


# --- organization members --------------------------------------------------


def test_the_creator_reaches_every_run_route(api, as_user, a_run):
    run, ref = a_run
    for path in RUN_READS + RUN_EXPORTS:
        assert api.get(fill(path, run, ref), headers=as_user("user-a1", "operator")).status_code == 200, path


def test_a_member_of_the_same_organization_shares_its_runs(api, as_user, a_run):
    """OD-2: the organization owns the run; RBAC still decides the operation."""
    run, ref = a_run
    headers = as_user("user-a2", "viewer")
    assert run in api.get("/api/v1/runs", headers=headers).text
    for path in RUN_READS:
        assert api.get(fill(path, run, ref), headers=headers).status_code == 200, path
    for path in RUN_EXPORTS:
        assert api.get(fill(path, run), headers=headers).status_code == 403, path


def test_the_creator_and_organization_are_recorded(api, as_user, a_run, a_batch, tmp_path):
    run, _ = a_run
    batch_id, child = a_batch
    with sqlite3.connect(tmp_path / "runs.db") as conn:
        for execution_id in (run, child):
            assert conn.execute(
                "SELECT organization_id, created_by_issuer, created_by_subject FROM execution_runs WHERE execution_id=?",
                (execution_id,)).fetchone() == (ORG_A, ISSUER, "user-a1")
        assert conn.execute(
            "SELECT organization_id, created_by_subject FROM batches WHERE batch_id=?", (batch_id,)
        ).fetchone() == (ORG_A, "user-a1")


@pytest.mark.parametrize(
    "method, path",
    [("POST", "/api/v1/runs"), ("POST", "/api/v1/runs/preview"), ("POST", "/api/v1/batches")],
)
def test_viewer_cannot_write(api, as_user, method, path):
    response = api.request(
        method, path, headers=as_user("user-a2", "viewer"),
        files={"file": ("v.xlsx", FIXTURE.read_bytes(), XLSX)}, data={"thresholds": THRESHOLDS, "fees": FEES},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "insufficient permissions"}


# --- another organization ----------------------------------------------------


def test_another_organization_does_not_see_the_run_in_listings(api, as_user, a_run):
    run, _ = a_run
    headers = as_user("user-b", "viewer")
    assert api.get("/api/v1/runs", headers=headers).json() == {"items": []}
    own = upload(api, as_user("user-b", "operator"), name="b.xlsx")
    items = api.get("/api/v1/runs", headers=headers).json()["items"]
    assert [item["execution_id"] for item in items] == [own]  # counters come from B's run only
    assert run not in json.dumps(items)


@pytest.mark.parametrize("path", RUN_READS)
def test_another_organization_cannot_read_the_run(api, as_user, a_run, path):
    run, ref = a_run
    same_as_absent(api, as_user("user-b", "viewer"), path, run, ref)


@pytest.mark.parametrize("path", RUN_EXPORTS)
def test_another_organization_cannot_export_or_download_the_run(api, as_user, a_run, path):
    run, _ = a_run
    same_as_absent(api, as_user("user-b", "operator"), path, run, "no-such-ref")


def test_an_admin_of_another_organization_gets_no_exception(api, as_user, a_run):
    """OD-4: the admin role grants every permission *within* its organization only."""
    run, ref = a_run
    for path in RUN_READS + RUN_EXPORTS:
        same_as_absent(api, as_user("user-b", "admin"), path, run, ref)
    listed = api.get("/api/v1/runs", headers=as_user("user-b", "admin")).json()
    assert run not in str(listed)


def test_another_organization_cannot_read_the_batch_or_its_runs(api, as_user, a_batch):
    batch_id, child = a_batch
    headers = as_user("user-b", "operator")
    assert api.get(f"/api/v1/batches/{batch_id}", headers=headers).content == \
        api.get(f"/api/v1/batches/{UNKNOWN_RUN}", headers=headers).content
    assert api.get(f"/api/v1/batches/{batch_id}", headers=headers).status_code == 404
    for path in ("/api/v1/runs/{run}/batch", *RUN_READS, *RUN_EXPORTS):
        same_as_absent(api, headers, path, child, "no-such-ref")
    assert api.get(f"/api/v1/batches/{batch_id}", headers=as_user("user-a2", "viewer")).status_code == 200


def test_record_pagination_of_another_organization_is_never_reached(api, as_user, a_run):
    run, _ = a_run
    for query in ("?limit=1&offset=0", "?limit=100&offset=1", "?decision=BUY", "?search=a"):
        response = api.get(f"/api/v1/runs/{run}/records{query}", headers=as_user("user-b", "viewer"))
        assert response.status_code == 404
        assert "pagination" not in response.text


# --- identities without an organization ------------------------------------


@pytest.mark.parametrize("method, path", DATA_ROUTES)
def test_an_identity_without_membership_gets_no_data_route(api, as_user, a_run, method, path):
    run, ref = a_run
    target = re.sub(r"\{execution_id\}", run, path)
    target = re.sub(r"\{record_ref\}", ref, target)
    target = re.sub(r"\{batch_id\}", UNKNOWN_RUN, target)
    response = api.request(method, target, headers=as_user("user-none", "admin"))
    assert response.status_code == 403
    assert response.json() == {"detail": "no organization access for this identity"}


def test_a_membership_under_another_issuer_does_not_apply(api, as_user, db):
    """`sub` is unique only per issuer: the same subject elsewhere is someone else."""
    db.add_membership(ORG_A, "https://other-issuer.example", "user-x", "test-operator", NOW)
    assert api.get("/api/v1/runs", headers=as_user("user-x", "admin")).status_code == 403


def test_a_second_organization_for_one_identity_is_refused(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.add_membership(ORG_B, ISSUER, "user-a1", "test-operator", NOW)


def test_oidc_without_a_store_answers_503_not_data(api, as_user, monkeypatch):
    monkeypatch.delenv("JUVAL_EXECUTION_DB_PATH")
    response = api.get("/api/v1/runs", headers=as_user("user-a1", "operator"))
    assert response.status_code == 503


# --- history without an owner (OD-3) ----------------------------------------


def test_a_run_without_an_owner_is_visible_to_nobody(api, as_user, db, tmp_path):
    legacy = ExecutionRun(
        execution_id="11111111-1111-4111-8111-111111111111", started_at=NOW, finished_at=NOW,
        status=ExecutionStatus.SUCCESS, input_filename="legacy.xlsx", input_hash="0" * 64,
        application_version="legacy", **COUNTS,
    )
    db.save_execution_run(legacy)  # unscoped tool, no owner: quarantined
    old_layout = tmp_path / "storage" / "juval_runs" / legacy.execution_id / "output.xlsx"
    old_layout.parent.mkdir(parents=True)
    old_layout.write_bytes(b"pre-partition export")
    for subject in ("user-a1", "user-b"):
        headers = as_user(subject, "operator")
        assert legacy.execution_id not in api.get("/api/v1/runs", headers=headers).text
        for path in RUN_READS + RUN_EXPORTS:
            assert api.get(fill(path, legacy.execution_id), headers=headers).status_code == 404, (subject, path)


# --- identifiers and errors ------------------------------------------------


@pytest.mark.parametrize("encoded", ["%2E%2E", "%2e%2e", "%2E", "..%5C..", "%2E%2E%5C%2E%2E"])
def test_a_dot_segment_never_leaves_the_organization_directory(api, as_user, encoded):
    """Regression (2026-11-10): `%2E%2E` used to serve `<storage>/output.xlsx`."""
    org_dir = service.storage_dir() / ORG_A
    org_dir.mkdir(parents=True)
    for outside in (service.storage_dir() / "output.xlsx", service.storage_dir().parent / "output.xlsx"):
        outside.write_bytes(b"outside-the-run-directory")
    response = api.get(f"/api/v1/runs/{encoded}/download", headers=as_user("user-a1", "operator"))
    assert response.status_code == 404
    assert b"outside-the-run-directory" not in response.content


@pytest.mark.parametrize("raw", ["", ".", "..", "a/b", "..\\x", "a\0b"])
def test_run_dir_refuses_anything_but_one_path_component(raw):
    with pytest.raises(ValueError):
        service.run_dir(ORG_A, raw)
    with pytest.raises(ValueError):
        service.run_dir(raw, UNKNOWN_RUN)


def test_manipulated_identifiers_do_not_alias_a_run(api, as_user, a_run):
    run, _ = a_run
    headers = as_user("user-a1", "viewer")
    for variant in (run.upper(), f"{run} ", f" {run}", f"{run}%00", run[:-1] + "%", run[:8] + "*", f"{run}' OR '1'='1"):
        response = api.get(f"/api/v1/runs/{variant}", headers=headers)
        assert response.status_code == 404, variant
        assert run not in response.text


def test_not_found_reveals_no_identifier_organization_or_path(api, as_user, a_run):
    run, _ = a_run
    for path in RUN_READS + RUN_EXPORTS:
        response = api.get(fill(path, run), headers=as_user("user-b", "operator"))
        assert response.status_code == 404, path
        for secret in (run, ORG_A, ORG_B, "storage", "juval_runs"):
            assert secret not in response.text, (path, secret)


# --- no route skips the check --------------------------------------------------


def _dependency_calls(dependant):
    for dependency in dependant.dependencies:
        yield dependency.call
        yield from _dependency_calls(dependency)


def test_every_data_route_resolves_the_organization():
    for route in app.routes:
        if getattr(route, "path", "").startswith("/api/v1/") and not route.path.startswith("/api/v1/auth"):
            assert tenant_access in set(_dependency_calls(route.dependant)), route.path


def test_every_run_route_authorizes_the_run_in_scope():
    """Download is the one exception: it reads only the caller's organization directory."""
    for route in app.routes:
        path = getattr(route, "path", "")
        if "{execution_id}" in path and not path.endswith("/download"):
            calls = _dependency_calls(route.dependant)
            assert any(getattr(call, "juval_authorizes", None) == "run" for call in calls), path


# --- the scoped store itself ---------------------------------------------------


def test_a_scoped_store_refuses_foreign_children_and_foreign_writes(db):
    run = ExecutionRun(
        execution_id="22222222-2222-4222-8222-222222222222", started_at=NOW, finished_at=NOW,
        status=ExecutionStatus.SUCCESS, input_filename="a.xlsx", input_hash="0" * 64, application_version="t", **COUNTS,
    )
    owner_a = Ownership(ORG_A, ISSUER, "user-a1")
    db.scoped(TenantScope(ORG_A)).save_execution_run(run, owner=owner_a)
    store_b = db.scoped(TenantScope(ORG_B))
    assert store_b.load_execution_run(run.execution_id) is None
    assert store_b.list_execution_runs() == []
    for read in (lambda: store_b.load_records(run.execution_id),
                 lambda: store_b.load_record(run.execution_id, "x"),
                 lambda: store_b.get_run_analytics(run.execution_id),
                 lambda: store_b.decision_counts([run.execution_id]),
                 lambda: store_b.load_financial_rows(run.execution_id)):
        with pytest.raises(OutOfScopeError):
            read()
    with pytest.raises(OutOfScopeError):
        store_b.save_execution_run(run, owner=owner_a)
    with pytest.raises(OutOfScopeError):
        store_b.save_execution_run(run)


def test_tenant_scope_accepts_only_canonical_uuids():
    for bad in ("", "..", ORG_A.upper(), "{" + ORG_A + "}", "not-a-uuid", ORG_A + "/x"):
        with pytest.raises(ValueError):
            TenantScope(bad)


# --- audit 2026-11-10: symlinks, spoofing, revocation, included routers --------


def test_a_symlink_never_serves_a_file_outside_the_organization(api, as_user, a_run, tmp_path):
    """Neither a symlinked output file nor a symlinked run directory leads out."""
    run, _ = a_run
    secret = tmp_path / "secret.xlsx"
    secret.write_bytes(b"outside-the-organization")
    headers = as_user("user-a1", "operator")
    linked_file = service.storage_dir() / ORG_A / "33333333-3333-4333-8333-333333333333"
    linked_file.mkdir()
    (linked_file / "output.xlsx").symlink_to(secret)
    (service.storage_dir() / ORG_A / "44444444-4444-4444-8444-444444444444").symlink_to(
        service.storage_dir() / ORG_A / run)  # inside the organization: still allowed
    org_b_dir = service.storage_dir() / ORG_B / "55555555-5555-4555-8555-555555555555"
    org_b_dir.mkdir(parents=True)
    (org_b_dir / "output.xlsx").write_bytes(b"organization-b-file")
    (service.storage_dir() / ORG_A / "66666666-6666-4666-8666-666666666666").symlink_to(org_b_dir)
    for target in (linked_file.name, "66666666-6666-4666-8666-666666666666"):
        response = api.get(f"/api/v1/runs/{target}/download", headers=headers)
        assert response.status_code == 404, target
        assert b"outside-the-organization" not in response.content and b"organization-b-file" not in response.content
    assert api.get("/api/v1/runs/44444444-4444-4444-8444-444444444444/download", headers=headers).status_code == 200


def test_the_request_cannot_choose_its_organization(api, as_user, a_run):
    """The organization comes only from the membership, never from the request."""
    run, _ = a_run
    for spoof in ({"headers": {"X-Organization-Id": ORG_A, "X-Tenant-Id": ORG_A}},
                  {"params": {"organization_id": ORG_A, "tenant": ORG_A}}):
        headers = {**as_user("user-b", "operator"), **spoof.get("headers", {})}
        assert api.get(f"/api/v1/runs/{run}", headers=headers, params=spoof.get("params")).status_code == 404
        assert api.get("/api/v1/runs", headers=headers, params=spoof.get("params")).json()["items"] == []


def test_removing_a_membership_ends_access_on_the_next_request(api, as_user, a_run, db):
    run, _ = a_run
    headers = as_user("user-a2", "viewer")
    assert api.get(f"/api/v1/runs/{run}", headers=headers).status_code == 200
    assert db.remove_membership(ISSUER, "user-a2") == ORG_A
    assert api.get(f"/api/v1/runs/{run}", headers=headers).status_code == 403   # same token, no membership


def test_included_routers_serve_no_data_route():
    """`app.routes` does not expand included routers, so the structural checks
    above cannot see their routes: only the BFF's /api/v1/auth may live there."""
    included = [route for route in app.routes if hasattr(route, "original_router")]
    assert included, "the BFF router is expected to be included"
    for router in included:
        for route in router.original_router.routes:
            assert route.path.startswith("/api/v1/auth/"), route.path
