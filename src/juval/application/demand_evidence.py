"""`juval.adr046.demand-evidence` v1: declared demand in a record snapshot (ADR-052).

Serialization only -- no validation against the clock on read (ADR-052 §20.9):
a stored document is reproduced exactly as captured. Instants keep the offset
they were declared or localized with; values keep their status, unit, raw value
and full provenance. Evidence only; nothing here feeds a decision.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from juval.domain.declared_demand import DeclaredDemandCapture

FORMAT = "juval.adr046.demand-evidence"
VERSION = 1
KEY = "demand_evidence"

DECLARED = "DECLARED"
NOT_DECLARED = "NOT_DECLARED"
NOT_CAPTURED = "NOT_CAPTURED"


def serialize_demand_evidence(capture: Optional[DeclaredDemandCapture]) -> Optional[dict[str, Any]]:
    """None when the file declared no demand columns (NOT_DECLARED)."""
    if capture is None:
        return None
    from juval.application.record_snapshot import _fv   # one FieldValue JSON shape for every snapshot field

    return {
        "format": FORMAT,
        "version": VERSION,
        "captured_at": capture.captured_at.isoformat(),
        "observations": [
            {
                "observation_id": item.observation_id,
                "metric": item.observation.metric.value,
                "value": _fv(item.observation.value),
                "observed_at": item.observation.observed_at.isoformat(),
                "window": {"start": item.observation.window.start.isoformat(), "end": item.observation.window.end.isoformat()},
                "window_source": item.window_source,
                "declared_month": item.declared_month,
                "declared_timezone": item.declared_timezone,
                "population_definition": item.observation.population_definition,
            }
            for item in sorted(capture.observations, key=lambda o: o.observation_id)
        ],
        "diagnostics": [
            {"code": d.code, "column": d.column, "row": d.row, "raw_value": d.raw_value, "message": d.message}
            for d in capture.diagnostics
        ],
    }


def demand_evidence_state(snapshot: Mapping[str, Any]) -> str:
    """NOT_CAPTURED (snapshot predates ADR-052), NOT_DECLARED (no demand
    columns in the file) or DECLARED (a document exists, usable or not)."""
    if KEY not in snapshot:
        return NOT_CAPTURED
    return NOT_DECLARED if snapshot[KEY] is None else DECLARED


def demand_export_cells(snapshot: Mapping[str, Any]) -> tuple[Any, ...]:
    """Same cells, same order as `exporter.demand_cells_from_capture`, read
    from a stored snapshot (so a historical one reports NOT_CAPTURED)."""
    from juval.infrastructure.excel.exporter import DEMAND_EXPORT_HEADERS

    state = demand_evidence_state(snapshot)
    blanks = (None,) * (len(DEMAND_EXPORT_HEADERS) - 1)
    document = snapshot.get(KEY)
    if state != DECLARED:
        return (state,) + blanks
    diagnostics = "; ".join(d["code"] for d in document.get("diagnostics", [])) or None
    observations = document.get("observations", [])
    if not observations:
        return (state,) + (None,) * (len(DEMAND_EXPORT_HEADERS) - 2) + (diagnostics,)
    first = observations[0]
    value = first["value"]
    provenance = value.get("provenance") or {}
    return (state, value.get("value"), value.get("status"), value.get("raw_value"),
            first["window"]["start"], first["window"]["end"], first["observed_at"], first["population_definition"],
            provenance.get("method"), provenance.get("source_reference"), diagnostics)
