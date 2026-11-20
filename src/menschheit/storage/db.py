"""Portable persistence layer (SQLite by default, PostgreSQL optional)."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.pool import StaticPool


def utcnow() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def jdumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def jloads(value: str | None, default: Any = None) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS debates (
        id TEXT PRIMARY KEY,
        topic TEXT NOT NULL,
        language TEXT NOT NULL,
        status TEXT NOT NULL,
        stop_reason TEXT,
        models_json TEXT NOT NULL,
        rounds_requested INTEGER NOT NULL,
        total_tokens INTEGER NOT NULL DEFAULT 0,
        cost_usd REAL NOT NULL DEFAULT 0,
        error TEXT,
        created_at TEXT NOT NULL,
        completed_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS turns (
        id TEXT PRIMARY KEY,
        debate_id TEXT NOT NULL REFERENCES debates(id) ON DELETE CASCADE,
        round_no INTEGER NOT NULL,
        role TEXT NOT NULL,
        steelman TEXT NOT NULL DEFAULT '',
        public_argument TEXT NOT NULL,
        internal_reasoning TEXT NOT NULL DEFAULT '',
        confidence INTEGER NOT NULL DEFAULT 50,
        conceded_json TEXT NOT NULL DEFAULT '[]',
        falsification TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS moderations (
        id TEXT PRIMARY KEY,
        debate_id TEXT NOT NULL REFERENCES debates(id) ON DELETE CASCADE,
        round_no INTEGER NOT NULL,
        summary TEXT NOT NULL,
        sycophancy INTEGER NOT NULL DEFAULT 0,
        drift INTEGER NOT NULL DEFAULT 0,
        decision TEXT NOT NULL,
        directive TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS judgments (
        id TEXT PRIMARY KEY,
        debate_id TEXT NOT NULL UNIQUE REFERENCES debates(id) ON DELETE CASCADE,
        pass_ab_json TEXT NOT NULL,
        pass_ba_json TEXT NOT NULL,
        bias_delta REAL NOT NULL DEFAULT 0,
        toulmin_json TEXT NOT NULL DEFAULT '{}',
        final_report_md TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engagements (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL DEFAULT 'default',
        client_name TEXT NOT NULL,
        roe_text TEXT NOT NULL,
        roe_hash TEXT NOT NULL,
        scope_json TEXT NOT NULL,
        ports_json TEXT NOT NULL,
        authorized_by TEXT NOT NULL,
        emergency_contact TEXT NOT NULL,
        valid_from TEXT NOT NULL,
        valid_until TEXT NOT NULL,
        kill_switch INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS actions (
        id TEXT PRIMARY KEY,
        engagement_id TEXT NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
        phase TEXT NOT NULL,
        target TEXT NOT NULL,
        port INTEGER NOT NULL,
        action_type TEXT NOT NULL,
        command TEXT NOT NULL,
        risk TEXT NOT NULL,
        expected_evidence TEXT NOT NULL,
        status TEXT NOT NULL,
        scope_allowed INTEGER NOT NULL,
        scope_reason TEXT NOT NULL DEFAULT '',
        approval_required INTEGER NOT NULL,
        approved_by TEXT,
        approved_at TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS findings (
        id TEXT PRIMARY KEY,
        engagement_id TEXT NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        owasp_ref TEXT NOT NULL DEFAULT '',
        cvss_vector TEXT NOT NULL DEFAULT '',
        evidence TEXT NOT NULL,
        remediation TEXT NOT NULL,
        verified_by_human INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_events (
        seq INTEGER PRIMARY KEY,
        id TEXT NOT NULL UNIQUE,
        engagement_id TEXT NOT NULL,
        actor TEXT NOT NULL,
        event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        prev_hash TEXT,
        hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_turns_debate ON turns(debate_id, round_no)",
    "CREATE INDEX IF NOT EXISTS idx_moderations_debate ON moderations(debate_id, round_no)",
    "CREATE INDEX IF NOT EXISTS idx_actions_engagement ON actions(engagement_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_findings_engagement ON findings(engagement_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_audit_engagement ON audit_events(engagement_id, seq)",
)


def _make_engine(url: str) -> Engine:
    kwargs: dict[str, Any] = {"future": True, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        if ":memory:" in url or url in {"sqlite://", "sqlite:///"}:
            kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
        if "sqlite:///" in url and ":memory:" not in url:
            raw_path = url.split("sqlite:///", 1)[1]
            if raw_path and not raw_path.startswith(":memory:"):
                Path(raw_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, **kwargs)


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self.engine = _make_engine(url)
        self._lock = threading.RLock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self.engine.begin() as conn:
            for statement in SCHEMA:
                conn.execute(text(statement))
            if self.engine.dialect.name == "sqlite":
                for trigger in (
                    """
                    CREATE TRIGGER IF NOT EXISTS audit_events_no_update
                    BEFORE UPDATE ON audit_events
                    BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END
                    """,
                    """
                    CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
                    BEFORE DELETE ON audit_events
                    BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END
                    """,
                ):
                    conn.execute(text(trigger))

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        with self._lock:
            with self.engine.begin() as conn:
                yield conn

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> None:
        with self._lock, self.engine.begin() as conn:
            conn.execute(text(sql), params or {})

    def fetch_one(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        with self._lock, self.engine.connect() as conn:
            row = conn.execute(text(sql), params or {}).mappings().first()
            return dict(row) if row else None

    def fetch_all(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self._lock, self.engine.connect() as conn:
            rows = conn.execute(text(sql), params or {}).mappings().all()
            return [dict(row) for row in rows]

    def health(self) -> bool:
        try:
            self.fetch_one("SELECT 1 AS ok")
            return True
        except Exception:
            return False
