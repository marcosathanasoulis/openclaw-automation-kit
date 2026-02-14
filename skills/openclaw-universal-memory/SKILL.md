---
name: openclaw-universal-memory
description: Connector-agnostic Postgres + pgvector memory ingestion and retrieval with incremental cursor history.
---

# OpenClaw Universal Memory

This skill provides a generic memory layer for heterogeneous data:
- canonical entity/chunk schema,
- connector-style ingestion with cursors,
- searchable memory in Postgres.

## Use Cases

- Normalize records from multiple systems into one schema.
- Keep incremental sync history (`cursor` per connector/account).
- Build RAG-ready chunk storage in pgvector.

## Prerequisites

- Postgres with `vector` extension.
- Local package installed: `pip install -e .`.
- Python dependency for DB I/O:
  - `pip install "psycopg[binary]>=3.2"`

## Commands

Initialize schema:

```bash
python skills/openclaw-universal-memory/scripts/run_memory.py \
  --action init-schema \
  --dsn "$DATABASE_DSN"
```

Ingest JSON/NDJSON:

```bash
python skills/openclaw-universal-memory/scripts/run_memory.py \
  --action ingest-json \
  --dsn "$DATABASE_DSN" \
  --source gmail \
  --account marcos@athanasoulis.net \
  --entity-type email \
  --input /path/to/records.ndjson
```

Search:

```bash
python skills/openclaw-universal-memory/scripts/run_memory.py \
  --action search \
  --dsn "$DATABASE_DSN" \
  --query "Deryk" \
  --limit 20
```

## Connector Contract (for custom adapters)

A connector returns normalized records + next cursor:

- `external_id`
- `entity_type`
- `title`
- `body_text`
- `raw_json`
- `meta_json`
- `next_cursor`

This keeps ingestion generic and supports arbitrary source systems.

