from __future__ import annotations

import json
from pathlib import Path

from openclaw_memory.chunking import split_text
from openclaw_memory.connectors.json_file import JsonFileConnector
from openclaw_memory.models import MemoryEntity


def test_memory_entity_is_stable() -> None:
    e1 = MemoryEntity.from_record(
        source="gmail",
        account="a@example.com",
        external_id="m-1",
        entity_type="email",
        title="Hello",
        body_text="Body",
        raw_json={"id": "m-1"},
    )
    e2 = MemoryEntity.from_record(
        source="gmail",
        account="a@example.com",
        external_id="m-1",
        entity_type="email",
        title="Hello",
        body_text="Body",
        raw_json={"id": "m-1"},
    )
    assert e1.entity_id == e2.entity_id
    assert e1.checksum == e2.checksum


def test_split_text_overlap() -> None:
    text = "abcdefghij"
    parts = split_text(text, chunk_chars=4, overlap_chars=1)
    assert parts == ["abcd", "defg", "ghij", "j"]


def test_json_file_connector_incremental(tmp_path: Path) -> None:
    path = tmp_path / "data.ndjson"
    rows = [
        {"id": "1", "title": "One", "body": "alpha"},
        {"id": "2", "title": "Two", "body": "beta"},
        {"id": "3", "title": "Three", "body": "gamma"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    conn = JsonFileConnector(
        source="test",
        account="acct",
        input_path=path,
        entity_type="note",
    )
    b1 = conn.fetch_incremental(cursor="0", limit=2)
    r1 = list(b1.records)
    assert len(r1) == 2
    assert b1.next_cursor == "2"
    assert r1[0].external_id == "1"

    b2 = conn.fetch_incremental(cursor=b1.next_cursor, limit=2)
    r2 = list(b2.records)
    assert len(r2) == 1
    assert r2[0].external_id == "3"


def test_universal_memory_schema_exists() -> None:
    repo = Path(__file__).resolve().parents[1]
    schema = repo / "schemas" / "universal_memory.sql"
    assert schema.exists()
    content = schema.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS um_entities" in content
    assert "CREATE TABLE IF NOT EXISTS um_chunks" in content
    assert "CREATE TABLE IF NOT EXISTS um_sync_state" in content
