from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List

from .models import MemoryChunk, MemoryEntity, SyncCheckpoint


class MissingDependencyError(RuntimeError):
    pass


class PostgresMemoryStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self):
        try:
            import psycopg
        except Exception as exc:  # pragma: no cover - import guard
            raise MissingDependencyError(
                "psycopg is not installed. Run: pip install 'psycopg[binary]>=3.2'"
            ) from exc
        return psycopg.connect(self._dsn)

    def apply_schema(self, schema_path: Path) -> None:
        sql = schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()

    def upsert_entities(self, entities: Iterable[MemoryEntity]) -> int:
        rows = list(entities)
        if not rows:
            return 0
        sql = """
        INSERT INTO um_entities (
            entity_id, source, account, external_id, entity_type, title, body_text,
            created_at_source, updated_at_source, raw_json, meta_json, checksum, ingested_at
        ) VALUES (
            %(entity_id)s, %(source)s, %(account)s, %(external_id)s, %(entity_type)s, %(title)s, %(body_text)s,
            %(created_at)s, %(updated_at)s, %(raw_json)s, %(meta_json)s, %(checksum)s, NOW()
        )
        ON CONFLICT (entity_id) DO UPDATE SET
            title = EXCLUDED.title,
            body_text = EXCLUDED.body_text,
            updated_at_source = EXCLUDED.updated_at_source,
            raw_json = EXCLUDED.raw_json,
            meta_json = EXCLUDED.meta_json,
            checksum = EXCLUDED.checksum,
            ingested_at = NOW()
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                for row in rows:
                    cur.execute(sql, asdict(row))
            conn.commit()
        return len(rows)

    def replace_chunks(self, entity_id: str, chunks: Iterable[MemoryChunk]) -> int:
        rows = list(chunks)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM um_chunks WHERE entity_id = %s", (entity_id,))
                for chunk in rows:
                    cur.execute(
                        """
                        INSERT INTO um_chunks (chunk_id, entity_id, chunk_index, chunk_text, meta_json)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (chunk_id) DO UPDATE SET
                            chunk_text = EXCLUDED.chunk_text,
                            meta_json = EXCLUDED.meta_json
                        """,
                        (
                            chunk.chunk_id,
                            chunk.entity_id,
                            chunk.chunk_index,
                            chunk.text,
                            chunk.meta_json,
                        ),
                    )
            conn.commit()
        return len(rows)

    def update_checkpoint(self, checkpoint: SyncCheckpoint) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO um_sync_state (connector, account, cursor, cursor_meta_json, updated_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (connector, account) DO UPDATE SET
                        cursor = EXCLUDED.cursor,
                        cursor_meta_json = EXCLUDED.cursor_meta_json,
                        updated_at = NOW()
                    """,
                    (
                        checkpoint.connector,
                        checkpoint.account,
                        checkpoint.cursor,
                        checkpoint.cursor_meta_json,
                    ),
                )
            conn.commit()

    def get_checkpoint(self, connector: str, account: str) -> str:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT cursor FROM um_sync_state WHERE connector=%s AND account=%s",
                    (connector, account),
                )
                row = cur.fetchone()
        return row[0] if row else "0"

    def search_keyword(self, query: str, limit: int = 10) -> List[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        e.source, e.account, e.entity_type, e.external_id, e.title,
                        c.chunk_text
                    FROM um_chunks c
                    JOIN um_entities e ON e.entity_id = c.entity_id
                    WHERE c.chunk_text ILIKE %s
                    ORDER BY e.updated_at_source DESC
                    LIMIT %s
                    """,
                    (f"%{query}%", limit),
                )
                rows = cur.fetchall()
        return [
            {
                "source": r[0],
                "account": r[1],
                "entity_type": r[2],
                "external_id": r[3],
                "title": r[4],
                "chunk_text": r[5],
            }
            for r in rows
        ]
