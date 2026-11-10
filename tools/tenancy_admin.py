"""Operator tool: organizations and memberships (ADR-056, OD-5/OD-6).

Memberships live in JUVAl's database and are changed only here, never by the
API or by self-service. Every change names who made it (`--created-by`), is
stored with it where the schema has a column for it, and is printed as one
audit line to keep with the access-review record (ACCESS_CONTROL.md).

    tenancy_admin.py --sqlite runs.db create-organization --name "Customer A" --created-by <operator>
    tenancy_admin.py --postgres-dsn-env JUVAL_TENANCY_ADMIN_DB_URL \\
        add-member --organization <uuid> --issuer <iss> --subject <sub> --created-by <operator>
    tenancy_admin.py ... remove-member --issuer <iss> --subject <sub> --created-by <operator>

PostgreSQL needs an administrative DSN (the runtime role `juval_backend` may
only read its own membership). The DSN is read from the named environment
variable, never from the command line, so it stays out of shell history and
process listings. `subject` is the IdP `sub` (FusionAuth user id), never an
email address; `issuer` is the exact `iss` the API verifies.

There is deliberately no command to assign unowned history (OD-3) and no
cross-organization role (OD-4).
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from juval.application.tenancy import LAB_ORGANIZATION_ID, canonical_organization_id

#: The loopback lab's issuer (ADR-055); it never authenticates anyone real.
LAB_ISSUER = "urn:juval:local-lab"


def _store(args):
    if args.sqlite:
        from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore

        return SqliteExecutionRunStore(Path(args.sqlite))
    dsn = os.environ.get(args.postgres_dsn_env)
    if not dsn:
        raise SystemExit(f"environment variable {args.postgres_dsn_env} is not set")
    from juval.infrastructure.persistence.supabase_execution_run_store import SupabaseExecutionRunStore

    return SupabaseExecutionRunStore(dsn)


def _identity(issuer: str, subject: str) -> tuple[str, str]:
    """Refuse identities that cannot be what the API verifies."""
    parts = urlsplit(issuer)
    if issuer == LAB_ISSUER or parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise SystemExit("--issuer must be the IdP's https issuer URL, exactly as in the token's iss claim")
    if not subject.strip() or subject != subject.strip() or "@" in subject:
        raise SystemExit("--subject must be the IdP sub (user id), not an email address or a padded value")
    return issuer, subject


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--sqlite", help="path of a local SQLite execution store")
    target.add_argument("--postgres-dsn-env", help="name of the environment variable holding an admin DSN")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-organization")
    create.add_argument("--name", required=True)
    member = commands.add_parser("add-member")
    member.add_argument("--organization", required=True)
    remove = commands.add_parser("remove-member")
    for command in (member, remove):
        command.add_argument("--issuer", required=True)
        command.add_argument("--subject", required=True)
    for command in (create, member, remove):
        command.add_argument("--created-by", required=True, help="who performs this change (audit trail)")
    args = parser.parse_args(argv)
    if not args.created_by.strip():
        raise SystemExit("--created-by must name the operator")

    now = datetime.now(timezone.utc)
    if args.command == "create-organization":
        organization_id = str(uuid.uuid4())
        _store(args).create_organization(organization_id, args.name, args.created_by, now)
        print(f"{now.isoformat()} create-organization {organization_id} name={args.name!r} by={args.created_by}")
        return 0

    issuer, subject = _identity(args.issuer, args.subject)
    if args.command == "remove-member":
        left = _store(args).remove_membership(issuer, subject)
        if left is None:
            raise SystemExit("no membership for this identity; nothing changed")
        print(f"{now.isoformat()} remove-member subject={subject} issuer={issuer} organization={left} by={args.created_by}")
        return 0

    organization_id = canonical_organization_id(args.organization)
    if organization_id == LAB_ORGANIZATION_ID:
        raise SystemExit("the loopback lab organization cannot have members")
    _store(args).add_membership(organization_id, issuer, subject, args.created_by, now)
    print(f"{now.isoformat()} add-member subject={subject} issuer={issuer} organization={organization_id} "
          f"by={args.created_by}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
