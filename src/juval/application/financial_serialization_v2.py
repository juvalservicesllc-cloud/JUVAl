"""Financial record format v2 (ADR-047 §19): v1 plus what v1 loses.

Same format identity, FORMAT = "juval.adr047.financial-record", VERSION = 2.
A v2 payload is the v1 record (`evidence`, `selling_price`, `resolution`,
`calculations`, encoded exactly as in v1) plus three explicit blocks:

  * `supplied_inputs`   the explicit inputs as they were handed to the
                        resolver, usable or not (NOT_FOUND, INVALID, wrong unit
                        or currency), or null when not supplied — v1 keeps only
                        a blocked input's blocker text;
  * `capture_problems`  the capturer's diagnostics for the record, verbatim;
  * `implementation`    the identity of the financial implementation that was
                        available when the record was built.

Version 1 is untouched and still read only by deserialize_financial_record;
`read_financial_record` dispatches explicitly on the version and never
reinterprets one as the other or fills v2 blocks for a v1 document.

Pure: no I/O, no calculation, no persistence. Nothing here is wired to the
CLI, SQLite, Supabase or the API.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Optional, Union

from juval.application.financial_calculation import EXPRESSIONS, SOURCE as CALCULATOR
from juval.application.financial_serialization import (
    CORE_KEYS,
    FORMAT,
    VERSION as V1,
    FinancialRecordDocument,
    FinancialSerializationError,
    _core_payload,
    _field,
    _obj,
    _parse_core,
    _parse_field,
    _str,
    _typed,
    _uniform_errors,
    _untyped,
    _versioned,
    deserialize_financial_record,
)
from juval.domain.financial_dependencies import DEPENDENCY_MATRIX, ExplicitInput, ResolutionBlocker
from juval.domain.provenance import FieldValue

VERSION = 2

_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _table_digest(table: Any) -> str:
    text = json.dumps(table, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def current_expressions_digest() -> str:
    """SHA-256 of the calculator's expression table as it exists in this code."""
    return _table_digest({result.value: text for result, text in EXPRESSIONS.items()})


def current_dependency_matrix_digest() -> str:
    """SHA-256 of ADR-047 §16's dependency matrix as it exists in this code."""
    return _table_digest({
        result.value: {"terms": [t.value for t in terms], "inputs": [i.value for i in inputs], "math": list(math)}
        for result, (terms, inputs, math) in DEPENDENCY_MATRIX.items()
    })


@dataclass(frozen=True)
class SuppliedInputs:
    """The resolver's explicit inputs as supplied; None means not supplied."""

    selling_price: Optional[FieldValue] = None
    weight: Optional[FieldValue] = None
    target_profit: Optional[FieldValue] = None
    target_roi: Optional[FieldValue] = None

    def get(self, name: ExplicitInput) -> Optional[FieldValue]:
        return getattr(self, name.value.lower())


@dataclass(frozen=True)
class CaptureProblem:
    """One capturer diagnostic. `text` is verbatim; the capturer does not yet emit
    structured subject/row/column/raw value, so those stay None unless supplied."""

    text: str
    subject: Optional[str] = None
    row: Optional[int] = None
    column: Optional[str] = None
    raw_value: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("A capture problem requires its text")
        if self.row is not None and (type(self.row) is not int or self.row < 1):
            raise ValueError("A capture problem row must be a positive integer")
        for name in ("subject", "column", "raw_value"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError(f"A capture problem {name} must be nonempty text when present")


@dataclass(frozen=True)
class ImplementationIdentity:
    """What is known about the implementation that built the record.

    The two digests identify the expression table and dependency matrix the
    code carried; they do not identify the functions behind them, the Python
    runtime or the environment. `application_version`, `code_revision` and
    `configuration` are None when unknown — never guessed or fabricated.
    `derivation_methods` lists approved derivation methods used (ADR-047 §15:
    none is approved today).
    """

    calculator: str
    expressions_digest: str
    dependency_matrix_digest: str
    application_version: Optional[str] = None
    code_revision: Optional[str] = None
    configuration: Optional[str] = None
    derivation_methods: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.calculator, str) or not self.calculator:
            raise ValueError("calculator identity is required")
        for name in ("expressions_digest", "dependency_matrix_digest"):
            if not isinstance(getattr(self, name), str) or not _DIGEST.match(getattr(self, name)):
                raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
        for name in ("application_version", "code_revision", "configuration"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be nonempty text or None (unknown)")
        if not isinstance(self.derivation_methods, tuple) or not all(
                isinstance(m, str) and m for m in self.derivation_methods):
            raise ValueError("derivation_methods must be a tuple of nonempty text")

    @classmethod
    def current(cls, *, application_version: Optional[str] = None, code_revision: Optional[str] = None,
                configuration: Optional[str] = None) -> "ImplementationIdentity":
        """Identity of this code's tables; the optional parts only as the caller knows them."""
        return cls(CALCULATOR, current_expressions_digest(), current_dependency_matrix_digest(),
                   application_version, code_revision, configuration)


@dataclass(frozen=True)
class FinancialRecordDocumentV2:
    document: FinancialRecordDocument
    supplied_inputs: SuppliedInputs
    capture_problems: tuple[CaptureProblem, ...]
    implementation: ImplementationIdentity

    def __post_init__(self) -> None:
        if not isinstance(self.document, FinancialRecordDocument):
            raise ValueError("Explicit FinancialRecordDocument required")
        if not isinstance(self.supplied_inputs, SuppliedInputs):
            raise ValueError("Explicit SuppliedInputs required")
        if not isinstance(self.implementation, ImplementationIdentity):
            raise ValueError("Explicit ImplementationIdentity required")
        if not isinstance(self.capture_problems, tuple) or not all(
                isinstance(p, CaptureProblem) for p in self.capture_problems):
            raise ValueError("capture_problems must be a tuple of CaptureProblem")
        if len(set(self.capture_problems)) != len(self.capture_problems):
            raise ValueError("capture_problems must not repeat a problem")
        _check_inputs(self)


def _check_inputs(doc: FinancialRecordDocumentV2) -> None:
    """Supplied inputs must be exactly what the stored resolution saw."""
    for name in ExplicitInput:
        value = doc.supplied_inputs.get(name)
        if value is not None and not isinstance(value, FieldValue):
            raise ValueError(f"supplied {name.value} must be a FieldValue or None")
    price = doc.document.selling_price
    if doc.supplied_inputs.selling_price != (price.amount if price is not None else None):
        raise ValueError("supplied selling price is not the record's declared selling price")
    if doc.document.resolution is None:
        return
    for item in doc.document.resolution.results:
        for dep in item.dependencies:
            if dep.term is not None or dep.dependency not in ExplicitInput.__members__:
                continue
            supplied = doc.supplied_inputs.get(ExplicitInput(dep.dependency))
            not_supplied = dep.blocker is ResolutionBlocker.STRUCTURALLY_ABSENT and dep.detail == "not supplied"
            if dep.operand is not None and dep.operand != supplied:
                raise ValueError(f"{dep.dependency} operand differs from the supplied input")
            if (supplied is None) != not_supplied:
                raise ValueError(f"{dep.dependency} supply state contradicts the resolution")


# -- reproducibility ---------------------------------------------------------------

@dataclass(frozen=True)
class ReproducibilityAssessment:
    """Unmet criteria per guarantee (ADR-047 §19); an empty tuple means it holds.

    A: exact recovery of the serialized state.
    B: complete reconstruction of the inputs as originally supplied.
    C: historical reproduction of the calculation — never asserted from the
       document alone, because it cannot prove the code and runtime it names.
    """

    state_recovery: tuple[str, ...]
    input_reconstruction: tuple[str, ...]
    historical_reproduction: tuple[str, ...]


def assess_reproducibility(
    document: Union[FinancialRecordDocument, FinancialRecordDocumentV2],
) -> ReproducibilityAssessment:
    if isinstance(document, FinancialRecordDocument):
        missing_inputs = ("format v1 does not record the explicit inputs as supplied",
                          "format v1 does not record capture problems")
        return ReproducibilityAssessment((), missing_inputs, (
            *missing_inputs, "format v1 does not record the implementation identity",
            "the code and runtime a document names cannot be verified from the document"))
    if not isinstance(document, FinancialRecordDocumentV2):
        raise ValueError("Explicit financial record document required")
    identity = document.implementation
    unmet = []
    if document.document.calculations is None:
        unmet.append("no calculation is recorded")
    if identity.application_version is None:
        unmet.append("application_version is unknown")
    if identity.code_revision is None:
        unmet.append("code_revision is unknown")
    if identity.expressions_digest != current_expressions_digest():
        unmet.append("expression table differs from the current code")
    if identity.dependency_matrix_digest != current_dependency_matrix_digest():
        unmet.append("dependency matrix differs from the current code")
    if document.document.evidence.scenario.context_requirements:
        unmet.append("scenario context requirements have no approved resolution method")
    unmet.append("the code and runtime a document names cannot be verified from the document")
    return ReproducibilityAssessment((), (), tuple(unmet))


# -- serialization -------------------------------------------------------------------

_V2_KEYS = frozenset({"format", "version", *CORE_KEYS, "supplied_inputs", "capture_problems", "implementation"})
_INPUT_KEYS = {name.value.lower() for name in ExplicitInput}


def serialize_financial_record_v2(document: FinancialRecordDocumentV2) -> dict[str, Any]:
    if not isinstance(document, FinancialRecordDocumentV2):
        raise FinancialSerializationError("Explicit FinancialRecordDocumentV2 required")
    identity = document.implementation
    return {
        "format": FORMAT,
        "version": VERSION,
        **_core_payload(document.document),
        "supplied_inputs": {key: _field(document.supplied_inputs.get(ExplicitInput(key.upper())))
                            for key in sorted(_INPUT_KEYS)},
        "capture_problems": [{"text": p.text, "subject": p.subject, "row": p.row, "column": p.column,
                              "raw_value": _typed(p.raw_value)} for p in document.capture_problems],
        "implementation": {
            "calculator": identity.calculator,
            "expressions_digest": identity.expressions_digest,
            "dependency_matrix_digest": identity.dependency_matrix_digest,
            "application_version": identity.application_version,
            "code_revision": identity.code_revision,
            "configuration": identity.configuration,
            "derivation_methods": list(identity.derivation_methods),
        },
    }


def deserialize_financial_record_v2(payload: Any) -> FinancialRecordDocumentV2:
    """Version 2 only; a v1 payload is rejected, not upgraded."""
    return _uniform_errors(_document_v2, payload)


def read_financial_record(payload: Any) -> Union[FinancialRecordDocument, FinancialRecordDocumentV2]:
    """Explicit dispatch on the stored version; unknown versions are rejected."""
    if not isinstance(payload, dict):
        raise FinancialSerializationError("payload must be an object")
    version = payload.get("version")
    if type(version) is int and version == V1:
        return deserialize_financial_record(payload)
    if type(version) is int and version == VERSION:
        return deserialize_financial_record_v2(payload)
    raise FinancialSerializationError(f"unsupported {FORMAT} version {version!r}")


def _document_v2(payload: Any) -> FinancialRecordDocumentV2:
    data = _versioned(payload, set(_V2_KEYS), VERSION)
    document = _parse_core(data)
    inputs = _obj(data["supplied_inputs"], "supplied_inputs", set(_INPUT_KEYS))
    supplied = SuppliedInputs(**{key: _parse_field(inputs[key], f"supplied_inputs.{key}") for key in _INPUT_KEYS})
    problems = []
    if not isinstance(data["capture_problems"], list):
        raise FinancialSerializationError("capture_problems must be a list")
    for i, raw in enumerate(data["capture_problems"]):
        where = f"capture_problems[{i}]"
        raw = _obj(raw, where, {"text", "subject", "row", "column", "raw_value"})
        row = raw["row"]
        if row is not None and type(row) is not int:
            raise FinancialSerializationError(f"{where}.row must be an integer or null")
        raw_value = _untyped(raw["raw_value"], f"{where}.raw_value")
        if raw_value is not None and not isinstance(raw_value, str):
            raise FinancialSerializationError(f"{where}.raw_value must be text")
        problems.append(CaptureProblem(
            text=_str(raw["text"], f"{where}.text"), subject=_str(raw["subject"], f"{where}.subject", optional=True),
            row=row, column=_str(raw["column"], f"{where}.column", optional=True), raw_value=raw_value))
    impl = _obj(data["implementation"], "implementation", {
        "calculator", "expressions_digest", "dependency_matrix_digest", "application_version", "code_revision",
        "configuration", "derivation_methods"})
    if not isinstance(impl["derivation_methods"], list):
        raise FinancialSerializationError("implementation.derivation_methods must be a list")
    identity = ImplementationIdentity(
        calculator=_str(impl["calculator"], "implementation.calculator"),
        expressions_digest=_str(impl["expressions_digest"], "implementation.expressions_digest"),
        dependency_matrix_digest=_str(impl["dependency_matrix_digest"], "implementation.dependency_matrix_digest"),
        application_version=_str(impl["application_version"], "implementation.application_version", optional=True),
        code_revision=_str(impl["code_revision"], "implementation.code_revision", optional=True),
        configuration=_str(impl["configuration"], "implementation.configuration", optional=True),
        derivation_methods=tuple(_str(m, "implementation.derivation_methods")
                                 for m in impl["derivation_methods"]))
    return FinancialRecordDocumentV2(document, supplied, tuple(problems), identity)
