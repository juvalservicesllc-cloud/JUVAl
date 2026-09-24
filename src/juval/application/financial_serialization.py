"""Versioned, reversible serialization of ADR-047 financial records.

Pure: native objects <-> a JSON-compatible dict. No I/O, no persistence, no
calculation on the way back — deserialization only rebuilds objects, and
every domain constructor re-validates its own invariants.

Format identity: FORMAT = "juval.adr047.financial-record", VERSION = 1. The
version identifies this serialization contract only, never a scenario,
policy or ADR version. An unknown format or version is rejected.

Encoding rules:
  * Decimal -> {"decimal": str(value)}: exact, sign and scale kept ("0.00"
    stays "0.00"); only the canonical str(Decimal) form is accepted back, and
    it is parsed with the Decimal constructor, which never rounds.
  * bool/str -> {"bool": ...}/{"str": ...}; absence -> null. No JSON floats
    for financial values (Provenance.confidence is the one non-financial float).
  * datetime -> ISO 8601 with offset; a naive or non-canonical text is rejected.
  * Enums by value; frozensets as value-sorted lists; tuples keep their order.
  * Every object has an exact key set: a missing or unknown key is rejected.

Sharing: a term dependency is written with its operand and applicability
inline *and* an `evidence_ref` to the record's evidence set. On the way back
the inline values must equal the referenced evidence and the rebuilt objects
are the evidence set's own, so references are restored within one document.
Explicit inputs (price, weight, targets) are inline and come back as equal,
not identical, objects. A calculation refers to its ResultResolution by
result name. No Python object identity beyond that is promised.

Determinism: serialize(deserialize(p)) == p for any accepted payload, and
the same objects always yield the same payload (canonical JSON via
json.dumps(sort_keys=True) is byte-identical).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Optional, TypeVar

from juval.application.financial_calculation import (
    CalculationBlocker,
    FinancialCalculation,
    FinancialCalculationSet,
    PreconditionCheck,
)
from juval.domain.financial_dependencies import (
    DependencyResolution,
    FinancialDependencyResolution,
    FinancialResult,
    ResolutionBlocker,
    ResultResolution,
)
from juval.domain.financial_evidence import (
    Applicability,
    DeclaredSellingPrice,
    EffectiveContext,
    FinancialDependency,
    FinancialEvidenceSet,
    FinancialScenario,
    FinancialTerm,
    FinancialTermEvidence,
)
from juval.domain.provenance import FieldValue, Provenance, SourceType, VerificationStatus

FORMAT = "juval.adr047.financial-record"
VERSION = 1

E = TypeVar("E", bound=Enum)


class FinancialSerializationError(ValueError):
    """A payload (or object) that does not satisfy this serialization contract."""


@dataclass(frozen=True)
class FinancialRecordDocument:
    """What one record's native financial state consists of, for serialization.

    `evidence` anchors the record; the other parts are optional and, when
    present, must belong to the same execution, record and scenario.
    """

    evidence: FinancialEvidenceSet
    selling_price: Optional[DeclaredSellingPrice] = None
    resolution: Optional[FinancialDependencyResolution] = None
    calculations: Optional[FinancialCalculationSet] = None


# -- serialize ---------------------------------------------------------------

def serialize_financial_record(document: FinancialRecordDocument) -> dict[str, Any]:
    if not isinstance(document, FinancialRecordDocument):
        raise FinancialSerializationError("Explicit FinancialRecordDocument required")
    return {"format": FORMAT, "version": VERSION, **_core_payload(document)}


#: Keys every version carries for the record itself (v2 adds its own blocks).
CORE_KEYS = frozenset({"evidence", "selling_price", "resolution", "calculations"})


def _core_payload(document: FinancialRecordDocument) -> dict[str, Any]:
    evidence = document.evidence
    _check_belongs(document)
    return {
        "evidence": _evidence_set(evidence),
        "selling_price": None if document.selling_price is None else {
            "amount": _field(document.selling_price.amount),
            "context": _context(document.selling_price.context),
        },
        "resolution": None if document.resolution is None else _resolution(document.resolution, evidence),
        "calculations": None if document.calculations is None else _calculations(document.calculations),
    }


def _check_belongs(document: FinancialRecordDocument) -> None:
    identity = (document.evidence.execution_id, document.evidence.record_reference)
    for part in (document.resolution, document.calculations):
        if part is not None and (part.execution_id, part.record_reference) != identity:
            raise FinancialSerializationError("resolution/calculations belong to another execution or record")
    if document.calculations is not None and document.resolution is None:
        raise FinancialSerializationError("calculations require the resolution they were computed from")
    if document.resolution is not None:
        for item in document.resolution.results:
            if item.scenario != document.evidence.scenario:
                raise FinancialSerializationError(f"{item.result.value} was resolved against another scenario")
            for dep in item.dependencies:
                if dep.evidence is not None and dep.evidence != document.evidence.evidence_for(dep.term):
                    raise FinancialSerializationError(f"{dep.dependency} evidence is not the record's evidence")
    if document.calculations is not None:
        for calc in document.calculations.calculations:
            if calc.resolution != document.resolution.for_result(calc.result):
                raise FinancialSerializationError(f"{calc.result.value} was not computed from this resolution")


def _typed(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return {"bool": value}
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise FinancialSerializationError(f"non-finite Decimal {value} is not serializable")
        return {"decimal": str(value)}
    if isinstance(value, str):
        return {"str": value}
    raise FinancialSerializationError(f"unsupported value type {type(value).__name__}")


def _field(fv: Optional[FieldValue]) -> Optional[dict[str, Any]]:
    if fv is None:
        return None
    p = fv.provenance
    if p.confidence is not None and (isinstance(p.confidence, bool) or not isinstance(p.confidence, (int, float))):
        raise FinancialSerializationError("confidence must be a number")
    return {
        "value": _typed(fv.value), "unit": fv.unit, "raw_value": _typed(fv.raw_value),
        "provenance": {
            "source": p.source, "source_type": p.source_type.value,
            "verification_status": p.verification_status.value,
            "retrieved_at": _instant(p.retrieved_at), "method": p.method,
            "confidence": None if p.confidence is None else float(p.confidence),
            "evidence": p.evidence, "source_reference": p.source_reference,
        },
    }


def _instant(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise FinancialSerializationError("naive datetime is not serializable")
    return value.isoformat()


def _context(context: EffectiveContext) -> dict[str, Any]:
    return {"effective_at": _instant(context.effective_at), "basis_definition": context.basis_definition,
            "effective_until": None if context.effective_until is None else _instant(context.effective_until)}


def _term_evidence(item: FinancialTermEvidence) -> dict[str, Any]:
    return {
        "term": item.term.value,
        "applicability": {"applies": _field(item.applicability.applies),
                          "justification": item.applicability.justification},
        "context": _context(item.context),
        "amount": _field(item.amount),
        "allocation_method": item.allocation_method,
        "depends_on": [{"reference": d.reference, "role": d.role, "term": None if d.term is None else d.term.value}
                       for d in item.depends_on],
    }


def _evidence_set(evidence: FinancialEvidenceSet) -> dict[str, Any]:
    s = evidence.scenario
    return {
        "scenario": {
            "scenario_id": s.scenario_id, "scenario_version": s.scenario_version, "currency": s.currency,
            "sellable_unit_definition": s.sellable_unit_definition, "policy_identity": s.policy_identity,
            "required_terms": sorted(term.value for term in s.required_terms),
            "context_requirements": list(s.context_requirements),
        },
        "execution_id": evidence.execution_id,
        "record_reference": evidence.record_reference,
        "terms": [_term_evidence(item) for item in evidence.terms],
    }


def _resolution(resolution: FinancialDependencyResolution, evidence: FinancialEvidenceSet) -> dict[str, Any]:
    return {
        "execution_id": resolution.execution_id,
        "record_reference": resolution.record_reference,
        "results": [{
            "result": item.result.value,
            "math_preconditions": list(item.math_preconditions),
            "dependencies": [{
                "dependency": dep.dependency,
                "term": None if dep.term is None else dep.term.value,
                "operand": _field(dep.operand),
                "applicability": _field(dep.applicability),
                "excluded": dep.excluded,
                "blocker": None if dep.blocker is None else dep.blocker.value,
                "detail": dep.detail,
                "evidence_ref": None if dep.evidence is None else dep.term.value,
            } for dep in item.dependencies],
        } for item in resolution.results],
    }


def _calculations(calculations: FinancialCalculationSet) -> dict[str, Any]:
    return {
        "execution_id": calculations.execution_id,
        "record_reference": calculations.record_reference,
        "decimal_precision": calculations.decimal_precision,
        "decimal_rounding": calculations.decimal_rounding,
        "calculations": [{
            "result": calc.result.value,
            "expression": calc.expression,
            "value": _field(calc.value),
            "preconditions": [{"expression": c.expression, "operand": _typed(c.operand), "satisfied": c.satisfied}
                              for c in calc.preconditions],
            "blocker": None if calc.blocker is None else calc.blocker.value,
            "undeclared_terms": [term.value for term in calc.undeclared_terms],
            "exact": calc.exact,
        } for calc in calculations.calculations],
    }


# -- deserialize ---------------------------------------------------------------

def deserialize_financial_record(payload: Any) -> FinancialRecordDocument:
    """Version 1 only; any other version (including 2) is rejected here."""
    return _uniform_errors(_document, payload)


def _uniform_errors(parse, payload: Any):
    try:
        return parse(payload)
    except FinancialSerializationError:
        raise
    except (ValueError, TypeError, KeyError) as error:
        # Domain constructors reject inconsistent content; report it uniformly.
        raise FinancialSerializationError(f"invalid financial record payload: {error}") from error


def _obj(data: Any, where: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise FinancialSerializationError(f"{where} must be an object")
    if set(data) != keys:
        raise FinancialSerializationError(
            f"{where} keys mismatch: missing {sorted(keys - set(data))}, unknown {sorted(set(data) - keys)}")
    return data


def _list(data: Any, where: str) -> list:
    if not isinstance(data, list):
        raise FinancialSerializationError(f"{where} must be a list")
    return data


def _str(data: Any, where: str, *, optional: bool = False) -> Optional[str]:
    if data is None and optional:
        return None
    if not isinstance(data, str):
        raise FinancialSerializationError(f"{where} must be a string")
    return data


def _bool(data: Any, where: str, *, optional: bool = False) -> Optional[bool]:
    if data is None and optional:
        return None
    if not isinstance(data, bool):
        raise FinancialSerializationError(f"{where} must be a boolean")
    return data


def _enum(kind: type[E], data: Any, where: str, *, optional: bool = False) -> Optional[E]:
    if data is None and optional:
        return None
    try:
        return kind(_str(data, where))
    except ValueError:
        raise FinancialSerializationError(f"{where}: {data!r} is not a {kind.__name__}") from None


def _decimal(text: Any, where: str) -> Decimal:
    text = _str(text, where)
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise FinancialSerializationError(f"{where}: {text!r} is not a decimal") from None
    if not value.is_finite() or str(value) != text:
        raise FinancialSerializationError(f"{where}: {text!r} is not a canonical finite decimal")
    return value


def _untyped(data: Any, where: str) -> Any:
    if data is None:
        return None
    if not isinstance(data, dict) or len(data) != 1:
        raise FinancialSerializationError(f"{where} must be null or a single-key typed value")
    [(kind, raw)] = data.items()
    if kind == "decimal":
        return _decimal(raw, where)
    if kind == "bool":
        return _bool(raw, where)
    if kind == "str":
        return _str(raw, where)
    raise FinancialSerializationError(f"{where}: unknown value type {kind!r}")


def _parse_instant(data: Any, where: str, *, optional: bool = False) -> Optional[datetime]:
    if data is None and optional:
        return None
    text = _str(data, where)
    try:
        value = datetime.fromisoformat(text)
    except ValueError:
        raise FinancialSerializationError(f"{where}: {text!r} is not an ISO 8601 instant") from None
    if value.tzinfo is None or value.utcoffset() is None or value.isoformat() != text:
        raise FinancialSerializationError(f"{where}: {text!r} must be a canonical instant with offset")
    return value


def _parse_field(data: Any, where: str) -> Optional[FieldValue]:
    if data is None:
        return None
    data = _obj(data, where, {"value", "unit", "raw_value", "provenance"})
    p = _obj(data["provenance"], f"{where}.provenance", {
        "source", "source_type", "verification_status", "retrieved_at", "method", "confidence", "evidence",
        "source_reference"})
    confidence = p["confidence"]
    if confidence is not None and (isinstance(confidence, bool) or not isinstance(confidence, (int, float))):
        raise FinancialSerializationError(f"{where}.provenance.confidence must be a number")
    provenance = Provenance(
        source=_str(p["source"], f"{where}.source"),
        source_type=_enum(SourceType, p["source_type"], f"{where}.source_type"),
        verification_status=_enum(VerificationStatus, p["verification_status"], f"{where}.verification_status"),
        retrieved_at=_parse_instant(p["retrieved_at"], f"{where}.retrieved_at"),
        method=_str(p["method"], f"{where}.method"),
        confidence=None if confidence is None else float(confidence),
        evidence=_str(p["evidence"], f"{where}.evidence", optional=True),
        source_reference=_str(p["source_reference"], f"{where}.source_reference", optional=True),
    )
    return FieldValue(value=_untyped(data["value"], f"{where}.value"), provenance=provenance,
                      unit=_str(data["unit"], f"{where}.unit", optional=True),
                      raw_value=_untyped(data["raw_value"], f"{where}.raw_value"))


def _parse_context(data: Any, where: str) -> EffectiveContext:
    data = _obj(data, where, {"effective_at", "basis_definition", "effective_until"})
    return EffectiveContext(effective_at=_parse_instant(data["effective_at"], f"{where}.effective_at"),
                            basis_definition=_str(data["basis_definition"], f"{where}.basis_definition"),
                            effective_until=_parse_instant(data["effective_until"], f"{where}.effective_until",
                                                           optional=True))


def _parse_term(data: Any, where: str) -> FinancialTermEvidence:
    data = _obj(data, where, {"term", "applicability", "context", "amount", "allocation_method", "depends_on"})
    applicability = _obj(data["applicability"], f"{where}.applicability", {"applies", "justification"})
    depends_on = []
    for i, dep in enumerate(_list(data["depends_on"], f"{where}.depends_on")):
        dep = _obj(dep, f"{where}.depends_on[{i}]", {"reference", "role", "term"})
        depends_on.append(FinancialDependency(
            reference=_str(dep["reference"], f"{where}.depends_on[{i}].reference"),
            role=_str(dep["role"], f"{where}.depends_on[{i}].role"),
            term=_enum(FinancialTerm, dep["term"], f"{where}.depends_on[{i}].term", optional=True)))
    return FinancialTermEvidence(
        term=_enum(FinancialTerm, data["term"], f"{where}.term"),
        applicability=Applicability(applies=_parse_field(applicability["applies"], f"{where}.applies"),
                                    justification=_str(applicability["justification"], f"{where}.justification")),
        context=_parse_context(data["context"], f"{where}.context"),
        amount=_parse_field(data["amount"], f"{where}.amount"),
        allocation_method=_str(data["allocation_method"], f"{where}.allocation_method", optional=True),
        depends_on=tuple(depends_on),
    )


def _parse_evidence(data: Any) -> FinancialEvidenceSet:
    data = _obj(data, "evidence", {"scenario", "execution_id", "record_reference", "terms"})
    s = _obj(data["scenario"], "scenario", {
        "scenario_id", "scenario_version", "currency", "sellable_unit_definition", "policy_identity",
        "required_terms", "context_requirements"})
    scenario = FinancialScenario(
        scenario_id=_str(s["scenario_id"], "scenario_id"),
        scenario_version=_str(s["scenario_version"], "scenario_version"),
        currency=_str(s["currency"], "currency"),
        sellable_unit_definition=_str(s["sellable_unit_definition"], "sellable_unit_definition"),
        policy_identity=_str(s["policy_identity"], "policy_identity"),
        required_terms=frozenset(_enum(FinancialTerm, t, "required_terms")
                                 for t in _list(s["required_terms"], "required_terms")),
        context_requirements=tuple(_str(r, "context_requirements")
                                   for r in _list(s["context_requirements"], "context_requirements")),
    )
    if len(set(s["required_terms"])) != len(s["required_terms"]):
        raise FinancialSerializationError("required_terms must not repeat a term")
    return FinancialEvidenceSet(
        scenario=scenario, execution_id=_str(data["execution_id"], "execution_id"),
        record_reference=_str(data["record_reference"], "record_reference"),
        terms=tuple(_parse_term(t, f"terms[{i}]") for i, t in enumerate(_list(data["terms"], "terms"))),
    )


def _shared(inline: Optional[FieldValue], canonical: Optional[FieldValue], where: str) -> Optional[FieldValue]:
    if inline is None:
        return None
    if inline != canonical:
        raise FinancialSerializationError(f"{where} does not match the referenced evidence")
    return canonical


def _parse_resolution(data: Any, evidence: FinancialEvidenceSet) -> FinancialDependencyResolution:
    data = _obj(data, "resolution", {"execution_id", "record_reference", "results"})
    results = []
    for i, item in enumerate(_list(data["results"], "resolution.results")):
        where = f"resolution.results[{i}]"
        item = _obj(item, where, {"result", "math_preconditions", "dependencies"})
        dependencies = []
        for j, dep in enumerate(_list(item["dependencies"], f"{where}.dependencies")):
            at = f"{where}.dependencies[{j}]"
            dep = _obj(dep, at, {"dependency", "term", "operand", "applicability", "excluded", "blocker", "detail",
                                 "evidence_ref"})
            term = _enum(FinancialTerm, dep["term"], f"{at}.term", optional=True)
            operand = _parse_field(dep["operand"], f"{at}.operand")
            applicability = _parse_field(dep["applicability"], f"{at}.applicability")
            linked = None
            if dep["evidence_ref"] is not None:
                ref = _enum(FinancialTerm, dep["evidence_ref"], f"{at}.evidence_ref")
                linked = evidence.evidence_for(ref)
                if ref != term or linked is None:
                    raise FinancialSerializationError(f"{at}.evidence_ref does not resolve to this term's evidence")
                operand = _shared(operand, linked.amount, f"{at}.operand")
                applicability = _shared(applicability, linked.applicability.applies, f"{at}.applicability")
            dependencies.append(DependencyResolution(
                dependency=_str(dep["dependency"], f"{at}.dependency"), term=term, operand=operand,
                applicability=applicability, excluded=_bool(dep["excluded"], f"{at}.excluded"),
                blocker=_enum(ResolutionBlocker, dep["blocker"], f"{at}.blocker", optional=True),
                detail=_str(dep["detail"], f"{at}.detail", optional=True), evidence=linked))
        results.append(ResultResolution(
            result=_enum(FinancialResult, item["result"], f"{where}.result"), scenario=evidence.scenario,
            dependencies=tuple(dependencies),
            math_preconditions=tuple(_str(m, f"{where}.math_preconditions")
                                     for m in _list(item["math_preconditions"], f"{where}.math_preconditions"))))
    resolution = FinancialDependencyResolution(
        execution_id=_str(data["execution_id"], "resolution.execution_id"),
        record_reference=_str(data["record_reference"], "resolution.record_reference"), results=tuple(results))
    if len({r.result for r in results}) != len(results):
        raise FinancialSerializationError("resolution repeats a result")
    return resolution


def _parse_calculations(data: Any, resolution: FinancialDependencyResolution) -> FinancialCalculationSet:
    data = _obj(data, "calculations", {"execution_id", "record_reference", "decimal_precision", "decimal_rounding",
                                       "calculations"})
    precision = data["decimal_precision"]
    if isinstance(precision, bool) or not isinstance(precision, int) or precision <= 0:
        raise FinancialSerializationError("decimal_precision must be a positive integer")
    by_result = {item.result: item for item in resolution.results}
    calculations = []
    for i, calc in enumerate(_list(data["calculations"], "calculations.calculations")):
        where = f"calculations[{i}]"
        calc = _obj(calc, where, {"result", "expression", "value", "preconditions", "blocker", "undeclared_terms",
                                  "exact"})
        result = _enum(FinancialResult, calc["result"], f"{where}.result")
        if result not in by_result:
            raise FinancialSerializationError(f"{where} refers to a result absent from the resolution")
        checks = []
        for j, check in enumerate(_list(calc["preconditions"], f"{where}.preconditions")):
            check = _obj(check, f"{where}.preconditions[{j}]", {"expression", "operand", "satisfied"})
            operand = _untyped(check["operand"], f"{where}.preconditions[{j}].operand")
            if not isinstance(operand, Decimal):
                raise FinancialSerializationError(f"{where}.preconditions[{j}].operand must be a decimal")
            checks.append(PreconditionCheck(_str(check["expression"], f"{where}.preconditions[{j}].expression"),
                                            operand, _bool(check["satisfied"], f"{where}.preconditions[{j}].satisfied")))
        blocker = _enum(CalculationBlocker, calc["blocker"], f"{where}.blocker", optional=True)
        value = _parse_field(calc["value"], f"{where}.value")
        exact = _bool(calc["exact"], f"{where}.exact", optional=True)
        # Coherence: a computed value is usable and has an exactness flag;
        # a blocked one is a NOT_FOUND with no exactness.
        if value is None or (blocker is None) != value.is_usable or (blocker is None) != (exact is not None):
            raise FinancialSerializationError(f"{where} value, blocker and exact are inconsistent")
        calculations.append(FinancialCalculation(
            result=result, expression=_str(calc["expression"], f"{where}.expression"),
            resolution=by_result[result], value=value, preconditions=tuple(checks), blocker=blocker,
            undeclared_terms=tuple(_enum(FinancialTerm, t, f"{where}.undeclared_terms")
                                   for t in _list(calc["undeclared_terms"], f"{where}.undeclared_terms")),
            exact=exact))
    if len({c.result for c in calculations}) != len(calculations):
        raise FinancialSerializationError("calculations repeat a result")
    return FinancialCalculationSet(
        execution_id=_str(data["execution_id"], "calculations.execution_id"),
        record_reference=_str(data["record_reference"], "calculations.record_reference"),
        calculations=tuple(calculations), decimal_precision=precision,
        decimal_rounding=_str(data["decimal_rounding"], "calculations.decimal_rounding"))


def _check_version(data: dict[str, Any], version: int) -> None:
    if data["format"] != FORMAT:
        raise FinancialSerializationError(f"unknown format {data['format']!r}")
    if type(data["version"]) is not int or data["version"] != version:
        raise FinancialSerializationError(f"unsupported {FORMAT} version {data['version']!r}")


def _versioned(payload: Any, keys: set[str], version: int) -> dict[str, Any]:
    """Identity first, so another version is reported as such, then the exact key set."""
    if isinstance(payload, dict) and "format" in payload and "version" in payload:
        _check_version(payload, version)
    data = _obj(payload, "payload", keys)
    _check_version(data, version)
    return data


def _document(payload: Any) -> FinancialRecordDocument:
    return _parse_core(_versioned(payload, {"format", "version", *CORE_KEYS}, VERSION))


def _parse_core(data: dict[str, Any]) -> FinancialRecordDocument:
    evidence = _parse_evidence(data["evidence"])
    price = None
    if data["selling_price"] is not None:
        p = _obj(data["selling_price"], "selling_price", {"amount", "context"})
        price = DeclaredSellingPrice(amount=_parse_field(p["amount"], "selling_price.amount"),
                                     context=_parse_context(p["context"], "selling_price.context"))
    resolution = None if data["resolution"] is None else _parse_resolution(data["resolution"], evidence)
    if data["calculations"] is not None and resolution is None:
        raise FinancialSerializationError("calculations require the resolution they were computed from")
    calculations = None if data["calculations"] is None else _parse_calculations(data["calculations"], resolution)
    document = FinancialRecordDocument(evidence, price, resolution, calculations)
    _check_belongs(document)
    return document
