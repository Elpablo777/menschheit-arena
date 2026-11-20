"""Schema: Debatten, Runden, Prompts, Provider-Katalog."""

from __future__ import annotations

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
        parent_debate_id TEXT,
        config_json TEXT NOT NULL DEFAULT '{}',
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
    CREATE TABLE IF NOT EXISTS llm_calls (
        id TEXT PRIMARY KEY,
        debate_id TEXT,
        engagement_id TEXT,
        role TEXT NOT NULL,
        purpose TEXT NOT NULL DEFAULT '',
        model TEXT NOT NULL DEFAULT '',
        round_no INTEGER,
        messages_json TEXT NOT NULL DEFAULT '[]',
        response_text TEXT NOT NULL DEFAULT '',
        parsed_ok INTEGER NOT NULL DEFAULT 0,
        error TEXT,
        prompt_tokens INTEGER NOT NULL DEFAULT 0,
        completion_tokens INTEGER NOT NULL DEFAULT 0,
        total_tokens INTEGER NOT NULL DEFAULT 0,
        duration_ms INTEGER NOT NULL DEFAULT 0,
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
    "CREATE INDEX IF NOT EXISTS idx_calls_debate ON llm_calls(debate_id, created_at)",
)

# Spalten, die bestehende Datenbanken nach dem ersten Start ergaenzt.
COLUMN_ADDITIONS: tuple[tuple[str, str, str], ...] = (
    ("debates", "parent_debate_id", "TEXT"),
    ("debates", "config_json", "TEXT NOT NULL DEFAULT '{}'"),
)


def migrate_columns(engine) -> list[str]:
    """Fuegt fehlende Spalten hinzu. Idempotent, funktioniert auf SQLite und Postgres."""
    added: list[str] = []
    if engine.dialect.name != "sqlite":
        return added
    from sqlalchemy import text

    with engine.begin() as conn:
        for table, column, definition in COLUMN_ADDITIONS:
            rows = conn.execute(text(f"PRAGMA table_info({table})")).mappings().all()
            names = {row["name"] for row in rows}
            if names and column not in names:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
                added.append(f"{table}.{column}")
    return added