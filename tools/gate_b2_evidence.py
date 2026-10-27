"""Offline-testable, deterministic Gate B2 evidence persistence.

Linux publication uses renameat2(RENAME_NOREPLACE): atomic visibility without
overwriting prior evidence. Neither SQL nor credentials are stored in diagnostics.
Catalog rows are unordered sets for serialization; SQL definition strings remain
intact unless they contain a connection URI. Classification never replaces facts.
"""
from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import re
import secrets
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

EVIDENCE_SCHEMA_VERSION = "1.0"
COLLECTOR_VERSION = "gate-b2-readonly/2"
DEFAULT_EVIDENCE_RELATIVE_PATH = Path(".local-evidence") / "gate_b2"
TARGET_RELATIONS = (
    "execution_runs", "execution_run_records", "execution_run_financial_records",
    "execution_run_capture_diagnostics", "batches", "batch_files",
    "identity_sessions", "identity_oauth_transactions",
)
ROLE_MATRIX = {
    name: {"SELECT", "INSERT"} for name in TARGET_RELATIONS
}
ROLE_MATRIX["identity_sessions"] |= {"UPDATE", "DELETE"}
ROLE_MATRIX["identity_oauth_transactions"] |= {"DELETE"}
DENIED_ROLES = ("anon", "authenticated", "authenticator", "service_role")
ALL_TABLE_PRIVILEGES = (
    "SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER", "MAINTAIN",
)
SENSITIVE_KEY = re.compile(
    r"(?:dsn|password|passwd|secret|credential|connection.?string|api.?key|token)", re.I,
)
CONNECTION_STRING = re.compile(r"(?i)\bpostgres(?:ql)?://[^\s\"']+")
LIFECYCLE_FLAGS = (
    "connection_established", "read_only_setup_complete", "read_only_verified",
    "observations_complete", "rollback_attempted", "rollback_succeeded",
    "connection_close_attempted", "connection_close_succeeded", "connection_closed",
)


class EvidenceNotFinalizable(ValueError):
    """Required transaction/connection lifecycle did not finish."""


class EvidencePathError(OSError):
    """Local evidence path is unsafe or publication failed."""


class EvidenceSecretError(ValueError):
    """Secret-bearing material must not become canonical evidence."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _safe_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _safe_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if not SENSITIVE_KEY.search(str(key))
        }
    if isinstance(value, (list, tuple, set)):
        items = [_safe_value(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(
            item, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
        ))
    if isinstance(value, str):
        return CONNECTION_STRING.sub("[REDACTED_CONNECTION_STRING]", value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise EvidenceSecretError("unsupported evidence value type")


def _assert_no_credential(value: Any) -> None:
    # Only the child's authorized DSN is examined, never any candidate file.
    # Reject known secret substrings even if embedded in an unexpected catalog
    # definition. Fail closed rather than claiming an unsanitized report is safe.
    dsn = os.environ.get("JUVAL_SUPABASE_DB_URL")
    if not dsn:
        return
    forbidden = {dsn}
    try:
        password = urlsplit(dsn).password
        if password:
            forbidden.update((password, unquote(password)))
    except ValueError:
        raise EvidenceSecretError("credential format cannot be safely checked") from None
    match = re.search(r"(?:^|\s)password\s*=\s*(?:'((?:\\.|[^'])*)'|([^\s]+))", dsn, re.I)
    if match:
        forbidden.add(re.sub(r"\\(.)", r"\1", match.group(1) or match.group(2)))

    def contains(item: Any) -> bool:
        if isinstance(item, str):
            return any(secret and secret in item for secret in forbidden)
        if isinstance(item, dict):
            return any(contains(key) or contains(part) for key, part in item.items())
        if isinstance(item, (list, tuple, set)):
            return any(contains(part) for part in item)
        return False

    if contains(value):
        raise EvidenceSecretError("credential-bearing evidence rejected")


def _validate_lifecycle(lifecycle: dict[str, Any]) -> None:
    if (
        type(lifecycle.get("attempt_count")) is not int
        or lifecycle["attempt_count"] != 1
        or lifecycle.get("transaction_read_only") != "on"
        or not all(lifecycle.get(key) is True for key in LIFECYCLE_FLAGS)
        or any(key.endswith("error_class") for key in lifecycle)
    ):
        raise EvidenceNotFinalizable("complete read-only rollback and close must be confirmed")


def reconcile_observations(catalog: dict[str, Any]) -> dict[str, Any]:
    """Conservative interpretation; missing evidence never implies absence."""
    rows = {row.get("name") or row.get("relname"): row for row in catalog.get("relations", [])}
    roles = {row.get("rolname") for row in catalog.get("roles", [])}
    relations = []
    for name in TARGET_RELATIONS:
        row = rows.get(name, {})
        effective = row.get("effective_table_privileges", {})
        acl = row.get("declared_acl_entries", [])
        origin = "UNDETERMINED"
        # A postgres grantor alone does not prove a manual JUVAl action.
        if any(entry.get("grantee") in ("anon", "authenticated", "service_role")
               and entry.get("grantor") in ("postgres", "supabase_admin") for entry in acl):
            origin = "SUPABASE_PLATFORM_DEFAULT_PLAUSIBLE"
        drift = row.get("state") == "PRESENT" and (
            row.get("rls_enabled") is False or row.get("rls_forced") is True
            or row.get("owner") == "juval_backend"
            or any(effective.get(role, {}).get(privilege) is True
                   for role in DENIED_ROLES for privilege in ALL_TABLE_PRIVILEGES)
            or any(entry.get("grantee") == "PUBLIC"
                   and entry.get("privilege_type") in ALL_TABLE_PRIVILEGES for entry in acl)
        )
        runtime = effective.get("juval_backend", {})
        if row.get("state") == "PRESENT" and "juval_backend" in roles:
            drift = drift or any(runtime.get(privilege) is False for privilege in ROLE_MATRIX[name])
            drift = drift or any(runtime.get(privilege) is True
                                 for privilege in ALL_TABLE_PRIVILEGES if privilege not in ROLE_MATRIX[name])
            drift = drift or ("policies" in row and row["policies"] == [])
        relations.append({
            "name": name,
            "object_control": "JUVAL_CONTROLLED",
            "security_state": "DRIFT" if drift else "UNDETERMINED",
            "grant_origin": origin,
            "reason": (
                "verified difference from ADR-048 target" if drift else
                "complete schema, effective access and policy semantics require reconciliation"
            ),
        })

    ledger = []
    for row in catalog.get("migration_ledger", {}).get("versions", []):
        state = row.get("state", "UNDETERMINED")
        candidate = row.get("version") == "20261005000007"
        ledger.append({
            "version": row.get("version"),
            "ledger_state": state,
            "material_schema_state": "UNDETERMINED",
            "security_state": (
                "EXPECTED" if candidate and state == "ABSENT" else
                "DRIFT" if candidate and state == "PRESENT" else "UNDETERMINED"
            ),
        })
    defaults = [{
        "owner": row.get("owner"), "schema": row.get("schema"),
        "object_type": row.get("object_type"), "grantee": row.get("grantee"),
        "privilege_type": row.get("privilege_type"),
        "object_control": "SUPABASE_MANAGED" if row.get("owner") == "supabase_admin" else "UNDETERMINED",
        "grant_origin": "SUPABASE_MANAGED" if row.get("owner") == "supabase_admin" else "UNDETERMINED",
        "security_state": "UNDETERMINED",
    } for row in catalog.get("default_privileges_by_owner", [])]
    capability = any(
        allowed is True
        for row in rows.values() if row.get("state") == "PRESENT"
        for privileges in row.get("effective_table_privileges", {}).values()
        for allowed in privileges.values()
    )
    return {
        "relations": relations, "ledger": ledger, "default_privileges": defaults,
        "postgresql_capability": "VERIFIED" if capability else "UNDETERMINED",
        "public_api_exploitability": "UNDETERMINED_NOT_TESTED",
    }


def build_evidence_document(
    catalog: dict[str, Any], lifecycle: dict[str, Any], *, timestamp_utc: str | None = None,
) -> dict[str, Any]:
    _validate_lifecycle(lifecycle)
    safe_catalog = _safe_value(catalog)
    _assert_no_credential(safe_catalog)
    return {
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "artifact_status": "VALID",
        "RAW_OBSERVATION": {
            "timestamp_utc": timestamp_utc or utc_now(),
            "collector_version": COLLECTOR_VERSION,
            "connection_lifecycle": {key: lifecycle[key] for key in (
                "attempt_count", "transaction_read_only", *LIFECYCLE_FLAGS,
            )},
            "observation_counts": {
                "target_relations": len(safe_catalog.get("relations", [])),
                "ledger_versions": len(safe_catalog.get("migration_ledger", {}).get("versions", [])),
                "roles": len(safe_catalog.get("roles", [])),
            },
            "catalog": safe_catalog,
        },
        "CLASSIFICATION": reconcile_observations(safe_catalog),
    }


def serialize_evidence(document: dict[str, Any]) -> bytes:
    if document.get("artifact_status") != "VALID" or document.get("evidence_schema_version") != EVIDENCE_SCHEMA_VERSION:
        raise EvidenceNotFinalizable("valid versioned evidence required")
    _validate_lifecycle(document.get("RAW_OBSERVATION", {}).get("connection_lifecycle", {}))
    safe = _safe_value(document)
    _assert_no_credential(safe)
    return (json.dumps(safe, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def _open_private_evidence_directory(repository_root: Path) -> int:
    # Walk EVERY component by descriptor with O_NOFOLLOW, including ancestors.
    if not repository_root.is_absolute() or ".." in repository_root.parts:
        raise EvidencePathError("absolute repository root without traversal required")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    parent = os.open("/", flags)
    try:
        for part in repository_root.parts[1:]:
            child = os.open(part, flags, dir_fd=parent)
            os.close(parent)
            parent = child
        root_info = os.fstat(parent)
        if root_info.st_uid != os.geteuid() or root_info.st_mode & 0o002:
            raise EvidencePathError("repository root ownership or permissions unsafe")
        for part in DEFAULT_EVIDENCE_RELATIVE_PATH.parts:
            try:
                os.mkdir(part, 0o700, dir_fd=parent)
            except FileExistsError:
                pass
            child = os.open(part, flags, dir_fd=parent)
            info = os.fstat(child)
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                os.close(child)
                raise EvidencePathError("evidence directory requires current owner and mode 0700")
            os.close(parent)
            parent = child
        return parent
    except OSError:
        os.close(parent)
        raise EvidencePathError("unsafe evidence directory") from None


def _rename_noreplace(directory_fd: int, temporary: str, final_name: str) -> None:
    """Linux atomic rename that refuses even a symlink at the destination."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        raise EvidencePathError("atomic no-overwrite rename unavailable")
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(directory_fd, os.fsencode(temporary), directory_fd, os.fsencode(final_name), 1):
        code = ctypes.get_errno()
        if code == errno.EEXIST:
            raise EvidencePathError("artifact exists; refusing overwrite")
        raise EvidencePathError("atomic artifact publication failed")


def write_evidence_artifact(
    document: dict[str, Any], *, repository_root: Path, timestamp_for_name: str | None = None,
) -> dict[str, str]:
    payload = serialize_evidence(document)
    stamp = timestamp_for_name or document["RAW_OBSERVATION"]["timestamp_utc"]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", stamp):
        raise EvidencePathError("invalid UTC artifact timestamp")
    nonce = secrets.token_hex(12)
    if not re.fullmatch(r"[0-9a-f]{24}", nonce):
        raise EvidencePathError("invalid artifact nonce")
    stamp = re.sub(r"[-:.]", "", stamp)
    temporary = f".gate-b2-{nonce}.tmp"
    final_name = f"gate-b2-{stamp}-{nonce}.json"
    root = Path(repository_root)
    directory = _open_private_evidence_directory(root)
    temp_exists = published = False
    file_fd = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
        file_fd = os.open(temporary, flags, 0o600, dir_fd=directory)
        temp_exists = True
        os.fchmod(file_fd, 0o600)
        original = os.fstat(file_fd)
        with os.fdopen(file_fd, "wb") as stream:
            file_fd = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        _rename_noreplace(directory, temporary, final_name)
        published, temp_exists = True, False
        fd = os.open(final_name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=directory)
        with os.fdopen(fd, "rb") as stream:
            final_info = os.fstat(stream.fileno())
            final_bytes = stream.read()
        if (
            final_info.st_ino != original.st_ino or final_info.st_dev != original.st_dev
            or not stat.S_ISREG(final_info.st_mode) or final_info.st_uid != os.geteuid()
            or stat.S_IMODE(final_info.st_mode) != 0o600 or final_bytes != payload
        ):
            raise EvidencePathError("published artifact validation failed")
        os.fsync(directory)
        artifact = {
            "path": str(root / DEFAULT_EVIDENCE_RELATIVE_PATH / final_name),
            "sha256": hashlib.sha256(final_bytes).hexdigest(),
            "bytes": str(len(final_bytes)),
        }
        _assert_no_credential(artifact)
        return artifact
    except (OSError, EvidenceSecretError):
        if published:
            os.unlink(final_name, dir_fd=directory)
            os.fsync(directory)
        raise EvidencePathError("artifact publication rejected") from None
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if temp_exists:
            os.unlink(temporary, dir_fd=directory)
        os.close(directory)


def compact_summary(document: dict[str, Any], artifact: dict[str, str]) -> dict[str, Any]:
    serialize_evidence(document)  # Revalidate lifecycle and secret exclusion.
    _assert_no_credential(artifact)
    raw = document["RAW_OBSERVATION"]
    catalog = raw["catalog"]
    relations = catalog.get("relations", [])
    versions = catalog.get("migration_ledger", {}).get("versions", [])
    present = sum(row.get("state") == "PRESENT" for row in relations)
    absent = sum(row.get("state") == "ABSENT" for row in relations)
    roles = catalog.get("roles")
    backend = (
        "PRESENT" if any(row.get("rolname") == "juval_backend" for row in roles or [])
        else "ABSENT" if roles is not None else "UNDETERMINED"
    )
    states = [row["security_state"] for row in document["CLASSIFICATION"]["relations"]]
    return {
        "artifact_path": artifact["path"], "sha256": artifact["sha256"],
        "evidence_schema_version": document["evidence_schema_version"],
        "artifact_status": "VALID", "collector_version": raw["collector_version"],
        "connection_attempts": raw["connection_lifecycle"]["attempt_count"],
        "connection_established": True, "transaction_read_only_verified": True,
        "rollback_attempted": True, "rollback_succeeded": True, "connection_closed": True,
        "target_relations_observed": present + absent,
        "target_relations_present": present, "target_relations_absent": absent,
        "target_relations_unobserved": len(TARGET_RELATIONS) - present - absent,
        "ledger_versions_present": sum(row.get("state") == "PRESENT" for row in versions),
        "ledger_versions_absent": sum(row.get("state") == "ABSENT" for row in versions),
        "juval_backend": backend,
        "classification_counts": {state: states.count(state) for state in ("DRIFT", "EXPECTED", "UNDETERMINED")},
        "secret_sanitization": "PASS",
    }
