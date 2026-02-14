from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .base import ConnectorBatch, NormalizedRecord


class JsonFileConnector:
    """Simple connector for JSON-array / NDJSON files used for local testing."""

    def __init__(
        self,
        *,
        source: str,
        account: str,
        input_path: Path,
        entity_type: str,
        id_field: str = "id",
        title_field: str = "title",
        body_field: str = "body",
    ) -> None:
        self.name = source
        self.account = account
        self.input_path = input_path
        self.entity_type = entity_type
        self.id_field = id_field
        self.title_field = title_field
        self.body_field = body_field

    def _load_rows(self) -> List[Dict[str, Any]]:
        raw = self.input_path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        if raw.startswith("["):
            data = json.loads(raw)
            if not isinstance(data, list):
                raise ValueError("JSON input must be an array")
            return [r for r in data if isinstance(r, dict)]
        rows = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
        return rows

    def fetch_incremental(self, cursor: str, limit: int = 500) -> ConnectorBatch:
        start = int(cursor or "0")
        rows = self._load_rows()
        selected = rows[start : start + max(1, limit)]
        normalized: List[NormalizedRecord] = []
        for idx, row in enumerate(selected, start=start):
            external_id = str(row.get(self.id_field) or f"row-{idx}")
            title = str(row.get(self.title_field) or external_id)
            body_text = str(row.get(self.body_field) or json.dumps(row, sort_keys=True))
            normalized.append(
                NormalizedRecord(
                    external_id=external_id,
                    entity_type=self.entity_type,
                    title=title,
                    body_text=body_text,
                    raw_json=row,
                    meta_json={"source_offset": idx},
                    created_at=None,
                    updated_at=None,
                )
            )
        next_cursor = str(start + len(selected))
        return ConnectorBatch(
            records=normalized,
            next_cursor=next_cursor,
            cursor_meta_json={"total_rows": len(rows)},
        )
