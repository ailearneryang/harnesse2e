"""SQLite-backed state and dedup storage for the harness runtime."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


class StateStore:
    """Persists runtime documents and webhook dedup state in SQLite."""

    def __init__(self, harness_dir: str):
        self.harness_dir = harness_dir
        self.db_path = os.path.join(harness_dir, "data", "harness_state.db")
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version < 1:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS state_documents (
                        name TEXT PRIMARY KEY,
                        payload TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS webhook_dedup (
                        dedup_key TEXT PRIMARY KEY,
                        source TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version INTEGER PRIMARY KEY,
                        applied_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    "INSERT OR REPLACE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (1, datetime.now().isoformat()),
                )
                conn.execute("PRAGMA user_version=1")
                conn.commit()

    def load_document(self, name: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM state_documents WHERE name = ?",
                (name,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["payload"])

    def save_document(self, name: str, payload: Dict[str, Any]) -> None:
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        now = datetime.now().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO state_documents(name, payload, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (name, serialized, now),
            )
            conn.commit()

    def claim_webhook_event(self, dedup_key: str, source: str, ttl_seconds: int = 3600) -> bool:
        cutoff = (datetime.now() - timedelta(seconds=ttl_seconds)).isoformat()
        now = datetime.now().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM webhook_dedup WHERE created_at < ?", (cutoff,))
            try:
                conn.execute(
                    "INSERT INTO webhook_dedup(dedup_key, source, created_at) VALUES (?, ?, ?)",
                    (dedup_key, source, now),
                )
            except sqlite3.IntegrityError:
                conn.rollback()
                return False
            conn.commit()
        return True
