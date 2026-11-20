"""SQLite-/Postgres-Zugriffsschicht mit append-only Audit-Kette."""

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

from .schema import SCHEMA, migrate_columns


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


def _normalise_action(row: dict[str, Any]) -> dict[str, Any]:
    row["scope_allowed"] = bool(row["scope_allowed"])
    row["approval_required"] = bool(row["approval_required"])
    return row


def _normalise_finding(row: dict[str, Any]) -> dict[str, Any]:
    row["verified_by_human"] = bool(row["verified_by_human"])
    return row


def _normalise_call(row: dict[str, Any]) -> dict[str, Any]:
    row["messages"] = jloads(row.pop("messages_json"), [])
    row["parsed_ok"] = bool(row.get("parsed_ok"))
    return row


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
        self.migrations: list[str] = []
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
        self.migrations = migrate_columns(self.engine)

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        with self._lock, self.engine.begin() as conn:
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