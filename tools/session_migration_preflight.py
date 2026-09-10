"""Read-only session migration packet; never executes migration or rollback SQL.

Default is offline. --check-database checks an already-migrated database using
JUVAL_SESSION_DB_URL exclusively, with the existing metadata-only startup check.
Missing/unmigrated databases fail the check; this tool never repairs them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from juval.infrastructure.persistence.postgres_session_store import verify_session_database

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = "supabase/migrations/20260909000004_identity_sessions.sql"
ROLLBACK = "supabase/migrations/20260909000004_identity_sessions.down.sql"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-database', action='store_true')
    args = parser.parse_args(argv)
    report = {
        'mode': 'READ_ONLY_PREFLIGHT',
        'live_migration_authorized': False,
        'backup_restore_evidence': 'OPERATOR_VERIFICATION_REQUIRED',
        'target_identity': 'OPERATOR_VERIFICATION_REQUIRED',
        'production_auth_admission': 'OPERATOR_VERIFICATION_REQUIRED',
        'pooler_refresh_guard': 'ISOLATED_ENDPOINT_VERIFICATION_REQUIRED',
        'rollback_effect': 'DELETES_SESSIONS_AND_OAUTH_TRANSACTIONS; SEPARATE_APPROVAL_REQUIRED',
        'database': 'NOT_CHECKED',
        'runbook': 'docs/compliance/IDENTITY_OPERATOR_CHECKPOINT.md',
    }
    try:
        report['artifacts'] = [
            {'path': path, 'sha256': hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}
            for path in (MIGRATION, ROLLBACK)
        ]
    except OSError:
        report['artifacts'] = 'MISSING_OR_UNREADABLE'
        print(json.dumps(report, indent=2))
        return 1
    if args.check_database:
        dsn = os.environ.get('JUVAL_SESSION_DB_URL')
        if not dsn:
            report['database'] = 'BLOCKED_MISSING_EXPLICIT_SESSION_DSN'
        else:
            try:
                verify_session_database(dsn)
                report['database'] = 'METADATA_READINESS_PASS_NOT_TARGET_OR_BACKUP_ATTESTATION'
            except Exception:
                # No driver exception, DSN, row, keyring or stack trace exported.
                report['database'] = 'METADATA_READINESS_FAIL'
    print(json.dumps(report, indent=2))
    return int(args.check_database and not report['database'].startswith('METADATA_READINESS_PASS'))


if __name__ == '__main__':
    raise SystemExit(main())
