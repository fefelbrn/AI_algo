"""SQLite metadata store — jobs, partitions, lineage."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class JobRun:
    run_id: str
    job_name: str
    status: str
    started_at: str
    completed_at: str | None
    code_version: str
    config_hashes: dict[str, str]
    input_partitions: dict[str, str]
    output_partitions: dict[str, str]


class MetadataStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_registry (
                    layer TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    column_count INTEGER NOT NULL,
                    registered_at TEXT NOT NULL,
                    PRIMARY KEY (layer, schema_version)
                );

                CREATE TABLE IF NOT EXISTS job_runs (
                    run_id TEXT PRIMARY KEY,
                    job_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    code_version TEXT NOT NULL,
                    config_hashes_json TEXT NOT NULL,
                    input_partitions_json TEXT NOT NULL,
                    output_partitions_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS data_partitions (
                    partition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    layer TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    partition_key TEXT NOT NULL,
                    partition_path TEXT NOT NULL,
                    record_count INTEGER NOT NULL DEFAULT 0,
                    schema_version TEXT NOT NULL,
                    version_id TEXT NOT NULL,
                    source_run_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (layer, partition_key, version_id)
                );

                CREATE TABLE IF NOT EXISTS lineage (
                    lineage_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    derived_partition_id INTEGER NOT NULL,
                    source_layer TEXT NOT NULL,
                    source_partition_key TEXT NOT NULL,
                    FOREIGN KEY (derived_partition_id) REFERENCES data_partitions(partition_id)
                );

                CREATE INDEX IF NOT EXISTS idx_partitions_layer_date
                    ON data_partitions (layer, trade_date);
                CREATE INDEX IF NOT EXISTS idx_job_runs_name
                    ON job_runs (job_name, started_at);
                """
            )

    def register_schema(self, layer: str, schema_version: str, column_count: int, registered_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO schema_registry
                (layer, schema_version, column_count, registered_at)
                VALUES (?, ?, ?, ?)
                """,
                (layer, schema_version, column_count, registered_at),
            )
            conn.commit()

    def start_job(
        self,
        run_id: str,
        job_name: str,
        *,
        code_version: str,
        config_hashes: dict[str, str],
        input_partitions: dict[str, str] | None = None,
        started_at: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO job_runs
                (run_id, job_name, status, started_at, completed_at, code_version,
                 config_hashes_json, input_partitions_json, output_partitions_json)
                VALUES (?, ?, 'running', ?, NULL, ?, ?, ?, '{}')
                """,
                (
                    run_id,
                    job_name,
                    started_at,
                    code_version,
                    json.dumps(config_hashes),
                    json.dumps(input_partitions or {}),
                ),
            )
            conn.commit()

    def complete_job(
        self,
        run_id: str,
        *,
        status: str,
        completed_at: str,
        output_partitions: dict[str, str],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE job_runs
                SET status = ?, completed_at = ?, output_partitions_json = ?
                WHERE run_id = ?
                """,
                (status, completed_at, json.dumps(output_partitions), run_id),
            )
            conn.commit()

    def register_partition(
        self,
        *,
        layer: str,
        trade_date: str,
        partition_key: str,
        partition_path: str,
        record_count: int,
        schema_version: str,
        version_id: str,
        source_run_id: str,
        created_at: str,
        source_layers: list[tuple[str, str]] | None = None,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT OR REPLACE INTO data_partitions
                (layer, trade_date, partition_key, partition_path, record_count,
                 schema_version, version_id, source_run_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    layer,
                    trade_date,
                    partition_key,
                    partition_path,
                    record_count,
                    schema_version,
                    version_id,
                    source_run_id,
                    created_at,
                ),
            )
            partition_id = cur.lastrowid or self._partition_id(conn, layer, partition_key, version_id)
            for src_layer, src_key in source_layers or []:
                conn.execute(
                    """
                    INSERT INTO lineage (derived_partition_id, source_layer, source_partition_key)
                    VALUES (?, ?, ?)
                    """,
                    (partition_id, src_layer, src_key),
                )
            conn.commit()
            return int(partition_id)

    def _partition_id(
        self,
        conn: sqlite3.Connection,
        layer: str,
        partition_key: str,
        version_id: str,
    ) -> int:
        row = conn.execute(
            """
            SELECT partition_id FROM data_partitions
            WHERE layer = ? AND partition_key = ? AND version_id = ?
            """,
            (layer, partition_key, version_id),
        ).fetchone()
        return int(row["partition_id"]) if row else 0

    def list_partitions(self, layer: str, trade_date: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM data_partitions
                WHERE layer = ? AND trade_date = ?
                ORDER BY created_at DESC
                """,
                (layer, trade_date),
            ).fetchall()
        return [dict(r) for r in rows]
