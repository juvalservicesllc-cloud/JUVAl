"""Preflight stays offline by default and never exports credential diagnostics."""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('session_preflight', Path(__file__).parents[2] / 'tools/session_migration_preflight.py')
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


def test_offline_packet_does_not_connect_even_with_runtime_dsn(monkeypatch, capsys):
    monkeypatch.setenv('JUVAL_SESSION_DB_URL', 'sensitive-value')
    monkeypatch.setattr(preflight, 'verify_session_database', lambda _: pytest.fail('unexpected I/O'))
    assert preflight.main([]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data['database'] == 'NOT_CHECKED'
    assert data['live_migration_authorized'] is False
    assert len(data['artifacts']) == 2
    assert all(len(x['sha256']) == 64 for x in data['artifacts'])


def test_explicit_check_never_falls_back_to_product_database(monkeypatch, capsys):
    monkeypatch.delenv('JUVAL_SESSION_DB_URL', raising=False)
    monkeypatch.setenv('JUVAL_SUPABASE_DB_URL', 'must-not-be-used')
    monkeypatch.setattr(preflight, 'verify_session_database', lambda _: pytest.fail('unexpected I/O'))
    assert preflight.main(['--check-database']) == 1
    assert json.loads(capsys.readouterr().out)['database'] == 'BLOCKED_MISSING_EXPLICIT_SESSION_DSN'


def test_driver_failure_is_sanitized(monkeypatch, capsys):
    monkeypatch.setenv('JUVAL_SESSION_DB_URL', 'sensitive-value')
    def fail(_):
        raise RuntimeError('sensitive-driver-diagnostic')
    monkeypatch.setattr(preflight, 'verify_session_database', fail)
    assert preflight.main(['--check-database']) == 1
    output = capsys.readouterr().out
    assert 'sensitive' not in output
    assert json.loads(output)['database'] == 'METADATA_READINESS_FAIL'


def test_success_does_not_attest_backup_or_authorize_migration(monkeypatch, capsys):
    monkeypatch.setenv('JUVAL_SESSION_DB_URL', 'synthetic')
    monkeypatch.setattr(preflight, 'verify_session_database', lambda _: None)
    assert preflight.main(['--check-database']) == 0
    data = json.loads(capsys.readouterr().out)
    assert data['backup_restore_evidence'] == 'OPERATOR_VERIFICATION_REQUIRED'
    assert data['live_migration_authorized'] is False
