from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from .chunking import chunk_entity_text
from .connectors import JsonFileConnector
from .models import MemoryEntity, SyncCheckpoint
from .store import MissingDependencyError, PostgresMemoryStore


def _pretty(data: Dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Universal memory skill CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init-schema", help="Apply universal memory schema")
    p_init.add_argument("--dsn", required=True)
    p_init.add_argument(
        "--schema-path",
        default=str(Path(__file__).resolve().parents[3] / "schemas" / "universal_memory.sql"),
    )

    p_ingest = sub.add_parser("ingest-json", help="Ingest JSON/NDJSON into universal schema")
    p_ingest.add_argument("--dsn", required=True)
    p_ingest.add_argument("--source", required=True)
    p_ingest.add_argument("--account", required=True)
    p_ingest.add_argument("--entity-type", required=True)
    p_ingest.add_argument("--input", required=True)
    p_ingest.add_argument("--limit", type=int, default=500)
    p_ingest.add_argument("--chunk-chars", type=int, default=1000)
    p_ingest.add_argument("--chunk-overlap", type=int, default=150)
    p_ingest.add_argument("--cursor", default="")
    p_ingest.add_argument("--id-field", default="id")
    p_ingest.add_argument("--title-field", default="title")
    p_ingest.add_argument("--body-field", default="body")

    p_search = sub.add_parser("search", help="Keyword search over ingested chunks")
    p_search.add_argument("--dsn", required=True)
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--limit", type=int, default=10)
    return p.parse_args()


def run_init_schema(args: argparse.Namespace) -> Dict[str, Any]:
    store = PostgresMemoryStore(args.dsn)
    schema_path = Path(args.schema_path).resolve()
    store.apply_schema(schema_path)
    return {"ok": True, "schema_path": str(schema_path)}


def run_ingest_json(args: argparse.Namespace) -> Dict[str, Any]:
    store = PostgresMemoryStore(args.dsn)
    connector = JsonFileConnector(
        source=args.source,
        account=args.account,
        input_path=Path(args.input).resolve(),
        entity_type=args.entity_type,
        id_field=args.id_field,
        title_field=args.title_field,
        body_field=args.body_field,
    )

    cursor = args.cursor or store.get_checkpoint(args.source, args.account)
    batch = connector.fetch_incremental(cursor=cursor, limit=args.limit)
    entities: List[MemoryEntity] = []
    total_chunks = 0

    for rec in batch.records:
        entity = MemoryEntity.from_record(
            source=args.source,
            account=args.account,
            external_id=rec.external_id,
            entity_type=rec.entity_type,
            title=rec.title,
            body_text=rec.body_text,
            raw_json=rec.raw_json,
            meta_json=rec.meta_json,
            created_at=rec.created_at,
            updated_at=rec.updated_at,
        )
        entities.append(entity)

    inserted = store.upsert_entities(entities)
    for entity in entities:
        chunks = chunk_entity_text(
            entity.entity_id,
            entity.body_text,
            chunk_chars=args.chunk_chars,
            overlap_chars=args.chunk_overlap,
        )
        total_chunks += store.replace_chunks(entity.entity_id, chunks)

    checkpoint = SyncCheckpoint.create(
        connector=args.source,
        account=args.account,
        cursor=batch.next_cursor,
        cursor_meta_json=batch.cursor_meta_json,
    )
    store.update_checkpoint(checkpoint)

    return {
        "ok": True,
        "source": args.source,
        "account": args.account,
        "entities_upserted": inserted,
        "chunks_upserted": total_chunks,
        "next_cursor": batch.next_cursor,
    }


def run_search(args: argparse.Namespace) -> Dict[str, Any]:
    store = PostgresMemoryStore(args.dsn)
    hits = store.search_keyword(args.query, limit=args.limit)
    return {"ok": True, "query": args.query, "hits": hits, "count": len(hits)}


def main() -> None:
    args = _parse_args()
    try:
        if args.cmd == "init-schema":
            print(_pretty(run_init_schema(args)))
            return
        if args.cmd == "ingest-json":
            print(_pretty(run_ingest_json(args)))
            return
        if args.cmd == "search":
            print(_pretty(run_search(args)))
            return
        raise RuntimeError(f"Unsupported command: {args.cmd}")
    except MissingDependencyError as exc:
        print(_pretty({"ok": False, "error": str(exc)}))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
