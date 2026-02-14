from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MemoryEntity:
    entity_id: str
    source: str
    account: str
    external_id: str
    entity_type: str
    title: str
    body_text: str
    created_at: str
    updated_at: str
    raw_json: Dict[str, Any]
    meta_json: Dict[str, Any]
    checksum: str

    @staticmethod
    def from_record(
        *,
        source: str,
        account: str,
        external_id: str,
        entity_type: str,
        title: str,
        body_text: str,
        raw_json: Dict[str, Any],
        meta_json: Optional[Dict[str, Any]] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> "MemoryEntity":
        canonical = json.dumps(
            {
                "source": source,
                "account": account,
                "external_id": external_id,
                "entity_type": entity_type,
                "title": title,
                "body_text": body_text,
            },
            sort_keys=True,
        )
        entity_id = stable_hash(f"{source}:{account}:{entity_type}:{external_id}")
        checksum = stable_hash(canonical)
        now = utc_now_iso()
        return MemoryEntity(
            entity_id=entity_id,
            source=source,
            account=account,
            external_id=external_id,
            entity_type=entity_type,
            title=title,
            body_text=body_text,
            created_at=created_at or now,
            updated_at=updated_at or now,
            raw_json=raw_json,
            meta_json=meta_json or {},
            checksum=checksum,
        )


@dataclass(frozen=True)
class MemoryChunk:
    chunk_id: str
    entity_id: str
    chunk_index: int
    text: str
    meta_json: Dict[str, Any]

    @staticmethod
    def from_text(entity_id: str, chunk_index: int, text: str) -> "MemoryChunk":
        chunk_id = stable_hash(f"{entity_id}:{chunk_index}:{text[:200]}")
        return MemoryChunk(
            chunk_id=chunk_id,
            entity_id=entity_id,
            chunk_index=chunk_index,
            text=text,
            meta_json={},
        )


@dataclass(frozen=True)
class SyncCheckpoint:
    connector: str
    account: str
    cursor: str
    cursor_meta_json: Dict[str, Any]
    updated_at: str

    @staticmethod
    def create(connector: str, account: str, cursor: str, cursor_meta_json: Dict[str, Any]) -> "SyncCheckpoint":
        return SyncCheckpoint(
            connector=connector,
            account=account,
            cursor=cursor,
            cursor_meta_json=cursor_meta_json,
            updated_at=utc_now_iso(),
        )
