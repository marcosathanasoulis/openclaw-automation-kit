from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Protocol


@dataclass(frozen=True)
class NormalizedRecord:
    external_id: str
    entity_type: str
    title: str
    body_text: str
    raw_json: Dict[str, Any]
    meta_json: Dict[str, Any]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class ConnectorBatch:
    records: Iterable[NormalizedRecord]
    next_cursor: str
    cursor_meta_json: Dict[str, Any]


class ConnectorProtocol(Protocol):
    name: str
    account: str

    def fetch_incremental(self, cursor: str, limit: int = 500) -> ConnectorBatch:
        """Return a normalized incremental batch and the next cursor."""

