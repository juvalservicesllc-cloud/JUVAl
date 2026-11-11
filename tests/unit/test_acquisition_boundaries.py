"""ADR-057/058 boundaries checked on the source itself (AST, no execution)."""

from __future__ import annotations

import ast
from pathlib import Path

import juval

SRC = Path(juval.__file__).parent
NETWORK_MODULES = {"socket", "ssl", "http", "urllib.request", "requests", "httpx", "httpx2", "aiohttp", "urllib3"}


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_transport_doubles_and_synthetic_contracts_live_only_in_tests():
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "ScriptedTransport" not in text and "synthetic.invalid" not in text, path
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                    isinstance(item, ast.FunctionDef) and item.name == "send" for item in node.body):
                bases = {getattr(b, "id", getattr(b, "attr", "")) for b in node.bases}
                assert "Protocol" in bases, f"{path}: {node.name} implements a transport outside tests/"


def test_no_network_code_in_the_acquisition_modules():
    for relative in ("infrastructure/enrichment/connector.py", "processing/acquisition_port.py",
                     "application/acquisition_run.py", "application/acquisition_documents.py",
                     "domain/acquisition.py"):
        found = imports(SRC / relative)
        assert not {m for m in found if m in NETWORK_MODULES or m.split(".")[0] in {"socket", "ssl", "requests",
                                                                                  "httpx", "aiohttp"}}, relative


def test_layers_point_inward():
    assert all(m.startswith("juval.domain") or not m.startswith("juval")
               for m in imports(SRC / "domain" / "acquisition.py"))
    assert all(m.startswith("juval.domain") or not m.startswith("juval")
               for m in imports(SRC / "processing" / "acquisition_port.py"))
    assert not any(m.startswith(("juval.infrastructure", "juval.interfaces"))
                   for m in imports(SRC / "application" / "acquisition_run.py"))


def test_processing_and_the_decision_engine_never_read_acquisition():  # ADR-058 I6, ADR-052 §20.3
    for path in (SRC / "processing").glob("*.py"):
        if path.name == "acquisition_port.py":
            continue
        assert not any("acquisition" in m for m in imports(path)), path
    for relative in ("domain/decision.py", "domain/product.py", "domain/sourcing_record.py"):
        assert not any("acquisition" in m for m in imports(SRC / relative)), relative


def test_no_connector_is_enabled_by_default():
    """No provider adapter exists in src/: nothing can be enabled without a new, authorized one."""
    enrichment = SRC / "infrastructure" / "enrichment"
    assert sorted(p.name for p in enrichment.glob("*.py")) == ["__init__.py", "connector.py"]
    for path in SRC.rglob("*.py"):
        assert "AuthorizedHttpConnector(" not in path.read_text(encoding="utf-8") or path.name == "connector.py", path
