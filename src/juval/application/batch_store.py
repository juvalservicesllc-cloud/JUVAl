"""Persistence port for auditable multi-file Batch groups."""

from __future__ import annotations

from typing import Optional, Protocol

from juval.domain.batch import Batch


class BatchStore(Protocol):
    def save_batch(self, batch: Batch) -> None:
        """Persist a batch and its ordered file outcomes atomically."""

    def load_batch(self, batch_id: str) -> Optional[Batch]:
        """Return a batch by its opaque grouping identity."""
