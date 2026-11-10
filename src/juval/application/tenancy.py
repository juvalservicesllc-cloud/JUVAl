"""Tenant scope and resource ownership (ADR-056).

A `TenantScope` is the organization a request acts for; it is resolved from
the caller's single membership (OD-5/OD-6) and never from the request itself.
An `Ownership` is what a new run or batch records: the organization that owns
it and who created it (OD-2, audit only -- access is per organization).

Organization ids are canonical lowercase UUIDs. That is checked here once, so
every layer can use an id as a SQL value and as a single path component
without re-validating it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

#: The fixed organization of the loopback lab (ADR-055/ADR-056 §9). It has no
#: row in `organizations`, so it can never be a customer's organization.
LAB_ORGANIZATION_ID = "00000000-0000-4000-8000-000000000001"


def canonical_organization_id(value: object) -> str:
    """`value` if it is a canonical lowercase UUID string, else ValueError."""
    if not isinstance(value, str):
        raise ValueError("organization id must be a string")
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        raise ValueError("organization id must be a UUID") from None
    if str(parsed) != value:
        raise ValueError("organization id must be a canonical lowercase UUID")
    return value


@dataclass(frozen=True)
class TenantScope:
    """The one organization whose data a request may read and write."""

    organization_id: str

    def __post_init__(self) -> None:
        canonical_organization_id(self.organization_id)


@dataclass(frozen=True)
class Ownership:
    """Owner and creator recorded on a new run or batch."""

    organization_id: str
    created_by_issuer: str
    created_by_subject: str

    def __post_init__(self) -> None:
        canonical_organization_id(self.organization_id)
        if not self.created_by_issuer or not self.created_by_subject:
            raise ValueError("ownership requires the creator's issuer and subject")


class OutOfScopeError(RuntimeError):
    """A scoped store was asked for a resource outside its organization.

    The API authorizes the parent run before reading its children, so this is
    a programming error, never a normal "not found": it fails loudly (500)
    instead of returning another organization's data or an empty answer.
    """
