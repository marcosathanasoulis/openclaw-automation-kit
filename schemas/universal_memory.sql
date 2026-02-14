-- Universal memory schema for connector-agnostic ingestion.
-- Designed for Postgres + pgvector (optional vector index path).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS um_entities (
    entity_id            TEXT PRIMARY KEY,
    source               TEXT NOT NULL,
    account              TEXT NOT NULL,
    external_id          TEXT NOT NULL,
    entity_type          TEXT NOT NULL,
    title                TEXT NOT NULL,
    body_text            TEXT NOT NULL,
    created_at_source    TIMESTAMPTZ,
    updated_at_source    TIMESTAMPTZ,
    raw_json             JSONB NOT NULL DEFAULT '{}'::jsonb,
    meta_json            JSONB NOT NULL DEFAULT '{}'::jsonb,
    checksum             TEXT NOT NULL,
    ingested_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source, account, entity_type, external_id)
);

CREATE INDEX IF NOT EXISTS idx_um_entities_source_account
    ON um_entities (source, account, entity_type, updated_at_source DESC);

CREATE TABLE IF NOT EXISTS um_chunks (
    chunk_id             TEXT PRIMARY KEY,
    entity_id            TEXT NOT NULL REFERENCES um_entities(entity_id) ON DELETE CASCADE,
    chunk_index          INTEGER NOT NULL,
    chunk_text           TEXT NOT NULL,
    meta_json            JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding            VECTOR(768),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (entity_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_um_chunks_entity
    ON um_chunks (entity_id, chunk_index);

CREATE INDEX IF NOT EXISTS idx_um_chunks_embedding
    ON um_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE IF NOT EXISTS um_relations (
    relation_id          TEXT PRIMARY KEY,
    from_entity_id       TEXT NOT NULL REFERENCES um_entities(entity_id) ON DELETE CASCADE,
    to_entity_id         TEXT NOT NULL REFERENCES um_entities(entity_id) ON DELETE CASCADE,
    relation_type        TEXT NOT NULL,
    meta_json            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (from_entity_id, to_entity_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_um_relations_from
    ON um_relations (from_entity_id, relation_type);

CREATE INDEX IF NOT EXISTS idx_um_relations_to
    ON um_relations (to_entity_id, relation_type);

CREATE TABLE IF NOT EXISTS um_sync_state (
    connector            TEXT NOT NULL,
    account              TEXT NOT NULL,
    cursor               TEXT NOT NULL,
    cursor_meta_json     JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (connector, account)
);

CREATE TABLE IF NOT EXISTS um_ingest_events (
    event_id             BIGSERIAL PRIMARY KEY,
    connector            TEXT NOT NULL,
    account              TEXT NOT NULL,
    status               TEXT NOT NULL,
    entities_count       INTEGER NOT NULL DEFAULT 0,
    chunks_count         INTEGER NOT NULL DEFAULT 0,
    cursor_before        TEXT,
    cursor_after         TEXT,
    error_message        TEXT,
    details_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at          TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_um_ingest_events_recent
    ON um_ingest_events (connector, account, started_at DESC);
