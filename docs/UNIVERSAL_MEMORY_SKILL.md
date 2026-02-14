# Universal Memory Skill

`openclaw-universal-memory` is a connector-agnostic ingestion skill for
Postgres + pgvector.

## What it provides

- canonical schema for heterogeneous records
- incremental sync cursors with per-connector history
- chunked text storage for retrieval and embedding backfill
- optional relation edges between entities

## Canonical tables

- `um_entities`: normalized records from any connector
- `um_chunks`: retrieval chunks per entity
- `um_relations`: optional links between entities
- `um_sync_state`: current cursor by connector/account
- `um_ingest_events`: ingestion history and failures

Schema file:
- `schemas/universal_memory.sql`

## Connector contract

Each connector returns normalized records:

- `external_id`
- `entity_type`
- `title`
- `body_text`
- `raw_json`
- `meta_json`

Plus checkpoint values:

- `next_cursor`
- `cursor_meta_json`

## Local usage

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
  --input /tmp/email.ndjson
```

Search:

```bash
python skills/openclaw-universal-memory/scripts/run_memory.py \
  --action search \
  --dsn "$DATABASE_DSN" \
  --query "Deryk" \
  --limit 20
```

## Migration pattern for existing assistants

1. Keep existing source-specific tables as-is.
2. Dual-write normalized records into `um_*` tables.
3. Validate query parity and freshness.
4. Move retrieval paths to `um_chunks` + vector search.
5. Retire legacy retrieval paths after burn-in.
