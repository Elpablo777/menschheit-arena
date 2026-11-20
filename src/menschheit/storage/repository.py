"""Repository mit parametrisierten Queries und append-only Audit-Kette."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy import text

from .db import Database, jdumps, jloads, utcnow


def new_id(prefix: str = "") -> str:
    value = uuid.uuid4().hex
    return f"{prefix}{value}" if prefix else value


def _normalise_action(row: dict[str, Any]) -> dict[str, Any]:
    row["scope_allowed"] = bool(row["scope_allowed"])
    row["approval_required"] = bool(row["approval_required"])
    return row


def _normalise_finding(row: dict[str, Any]) -> dict[str, Any]:
    row["verified_by_human"] = bool(row["verified_by_human"])
    return row


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ---------- Arena ----------

    def create_debate(
        self,
        topic: str,
        language: str,
        rounds_requested: int,
        models: dict[str, str],
    ) -> dict[str, Any]:
        debate_id = new_id("deb_")
        now = utcnow()
        self.db.execute(
            """
            INSERT INTO debates (id, topic, language, status, models_json, rounds_requested, created_at)
            VALUES (:id, :topic, :language, 'pending', :models, :rounds, :created)
            """,
            {
                "id": debate_id,
                "topic": topic,
                "language": language,
                "models": jdumps(models),
                "rounds": rounds_requested,
                "created": now,
            },
        )
        return self.get_debate(debate_id) or {}

    def update_debate(self, debate_id: str, **fields: Any) -> None:
        allowed = {"status", "stop_reason", "total_tokens", "cost_usd", "error", "completed_at"}
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            return
        assignments = ", ".join(f"{key} = :{key}" for key in updates)
        updates["debate_id"] = debate_id
        self.db.execute(f"UPDATE debates SET {assignments} WHERE id = :debate_id", updates)

    def get_debate(self, debate_id: str) -> dict[str, Any] | None:
        row = self.db.fetch_one("SELECT * FROM debates WHERE id = :id", {"id": debate_id})
        if not row:
            return None
        row["models"] = jloads(row.pop("models_json"), {})
        row["turns"] = self.list_turns(debate_id)
        row["moderations"] = self.list_moderations(debate_id)
        judgment = self.get_judgment(debate_id)
        row["judgment"] = judgment
        return row

    def fail_stale_debates(self) -> None:
        self.db.execute(
            "UPDATE debates SET status = 'failed', stop_reason = 'ERROR', "
            "error = 'Server wurde neu gestartet, waehrend die Debatte lief.', "
            "completed_at = :now WHERE status = 'running'",
            {"now": utcnow()},
        )

    def list_debates(self, limit: int = 40) -> list[dict[str, Any]]:
        rows = self.db.fetch_all(
            "SELECT id, topic, language, status, stop_reason, created_at, completed_at "
            "FROM debates ORDER BY created_at DESC LIMIT :limit",
            {"limit": max(1, min(limit, 200))},
        )
        return rows

    def add_turn(
        self,
        debate_id: str,
        round_no: int,
        role: str,
        steelman: str,
        public_argument: str,
        internal_reasoning: str,
        confidence: int,
        conceded: list[str],
        falsification: str,
    ) -> str:
        turn_id = new_id("turn_")
        self.db.execute(
            """
            INSERT INTO turns
                (id, debate_id, round_no, role, steelman, public_argument, internal_reasoning,
                 confidence, conceded_json, falsification, created_at)
            VALUES
                (:id, :debate_id, :round_no, :role, :steelman, :public, :internal,
                 :confidence, :conceded, :falsification, :created)
            """,
            {
                "id": turn_id,
                "debate_id": debate_id,
                "round_no": round_no,
                "role": role,
                "steelman": steelman,
                "public": public_argument,
                "internal": internal_reasoning,
                "confidence": max(0, min(100, int(confidence))),
                "conceded": jdumps(conceded),
                "falsification": falsification,
                "created": utcnow(),
            },
        )
        return turn_id

    def list_turns(self, debate_id: str) -> list[dict[str, Any]]:
        rows = self.db.fetch_all(
            "SELECT * FROM turns WHERE debate_id = :id ORDER BY round_no, created_at, id",
            {"id": debate_id},
        )
        for row in rows:
            row["conceded_claims"] = jloads(row.pop("conceded_json"), [])
        return rows

    def add_moderation(
        self,
        debate_id: str,
        round_no: int,
        summary: str,
        sycophancy: bool,
        drift: bool,
        decision: str,
        directive: str,
    ) -> str:
        moderation_id = new_id("mod_")
        self.db.execute(
            """
            INSERT INTO moderations
                (id, debate_id, round_no, summary, sycophancy, drift, decision, directive, created_at)
            VALUES
                (:id, :debate_id, :round_no, :summary, :sycophancy, :drift, :decision, :directive, :created)
            """,
            {
                "id": moderation_id,
                "debate_id": debate_id,
                "round_no": round_no,
                "summary": summary,
                "sycophancy": int(sycophancy),
                "drift": int(drift),
                "decision": decision,
                "directive": directive,
                "created": utcnow(),
            },
        )
        return moderation_id

    def list_moderations(self, debate_id: str) -> list[dict[str, Any]]:
        rows = self.db.fetch_all(
            "SELECT * FROM moderations WHERE debate_id = :id ORDER BY round_no, created_at, id",
            {"id": debate_id},
        )
        for row in rows:
            row["sycophancy"] = bool(row["sycophancy"])
            row["drift"] = bool(row["drift"])
        return rows

    def save_judgment(
        self,
        debate_id: str,
        pass_ab: dict[str, Any],
        pass_ba: dict[str, Any],
        bias_delta: float,
        toulmin: dict[str, Any],
        final_report_md: str,
    ) -> str:
        judgment_id = new_id("jud_")
        existing = self.db.fetch_one("SELECT id FROM judgments WHERE debate_id = :id", {"id": debate_id})
        if existing:
            self.db.execute(
                """
                UPDATE judgments
                SET pass_ab_json = :ab, pass_ba_json = :ba, bias_delta = :delta,
                    toulmin_json = :toulmin, final_report_md = :report, created_at = :created
                WHERE debate_id = :debate_id
                """,
                {
                    "ab": jdumps(pass_ab),
                    "ba": jdumps(pass_ba),
                    "delta": float(bias_delta),
                    "toulmin": jdumps(toulmin),
                    "report": final_report_md,
                    "created": utcnow(),
                    "debate_id": debate_id,
                },
            )
            return str(existing["id"])
        self.db.execute(
            """
            INSERT INTO judgments
                (id, debate_id, pass_ab_json, pass_ba_json, bias_delta, toulmin_json,
                 final_report_md, created_at)
            VALUES
                (:id, :debate_id, :ab, :ba, :delta, :toulmin, :report, :created)
            """,
            {
                "id": judgment_id,
                "debate_id": debate_id,
                "ab": jdumps(pass_ab),
                "ba": jdumps(pass_ba),
                "delta": float(bias_delta),
                "toulmin": jdumps(toulmin),
                "report": final_report_md,
                "created": utcnow(),
            },
        )
        return judgment_id

    def get_judgment(self, debate_id: str) -> dict[str, Any] | None:
        row = self.db.fetch_one("SELECT * FROM judgments WHERE debate_id = :id", {"id": debate_id})
        if not row:
            return None
        row["pass_ab"] = jloads(row.pop("pass_ab_json"), {})
        row["pass_ba"] = jloads(row.pop("pass_ba_json"), {})
        row["toulmin"] = jloads(row.pop("toulmin_json"), {})
        return row

    # ---------- Sentinel ----------

    def create_engagement(
        self,
        client_name: str,
        roe_text: str,
        roe_hash: str,
        scope: list[str],
        ports: list[int],
        authorized_by: str,
        emergency_contact: str,
        valid_from: str,
        valid_until: str,
        tenant_id: str = "default",
    ) -> dict[str, Any]:
        engagement_id = new_id("eng_")
        self.db.execute(
            """
            INSERT INTO engagements
                (id, tenant_id, client_name, roe_text, roe_hash, scope_json, ports_json,
                 authorized_by, emergency_contact, valid_from, valid_until, created_at)
            VALUES
                (:id, :tenant, :client, :roe, :hash, :scope, :ports, :authorized,
                 :emergency, :valid_from, :valid_until, :created)
            """,
            {
                "id": engagement_id,
                "tenant": tenant_id,
                "client": client_name,
                "roe": roe_text,
                "hash": roe_hash,
                "scope": jdumps(scope),
                "ports": jdumps(ports),
                "authorized": authorized_by,
                "emergency": emergency_contact,
                "valid_from": valid_from,
                "valid_until": valid_until,
                "created": utcnow(),
            },
        )
        return self.get_engagement(engagement_id) or {}

    def get_engagement(self, engagement_id: str) -> dict[str, Any] | None:
        row = self.db.fetch_one("SELECT * FROM engagements WHERE id = :id", {"id": engagement_id})
        if not row:
            return None
        row["kill_switch"] = bool(row["kill_switch"])
        row["scope"] = jloads(row.pop("scope_json"), [])
        row["ports"] = jloads(row.pop("ports_json"), [])
        row["actions"] = [_normalise_action(action) for action in self.list_actions(engagement_id)]
        row["findings"] = [_normalise_finding(finding) for finding in self.list_findings(engagement_id)]
        row["audit"] = self.list_audit(engagement_id)
        row["audit_valid"] = self.verify_audit_chain(engagement_id)[0]
        return row

    def list_engagements(self, limit: int = 40) -> list[dict[str, Any]]:
        rows = self.db.fetch_all(
            "SELECT id, client_name, status, valid_from, valid_until, kill_switch, created_at "
            "FROM engagements ORDER BY created_at DESC LIMIT :limit",
            {"limit": max(1, min(limit, 200))},
        )
        for row in rows:
            row["kill_switch"] = bool(row["kill_switch"])
        return rows

    def set_kill_switch(self, engagement_id: str, active: bool) -> None:
        self.db.execute(
            "UPDATE engagements SET kill_switch = :active, status = :status WHERE id = :id",
            {"active": int(active), "status": "killed" if active else "active", "id": engagement_id},
        )
        if active:
            self.db.execute(
                "UPDATE actions SET status = 'rejected' "
                "WHERE engagement_id = :id AND status IN ('proposed', 'approved')",
                {"id": engagement_id},
            )

    def add_action(
        self,
        engagement_id: str,
        phase: str,
        target: str,
        port: int,
        action_type: str,
        command: str,
        risk: str,
        expected_evidence: str,
        scope_allowed: bool,
        scope_reason: str,
        approval_required: bool,
    ) -> dict[str, Any]:
        action_id = new_id("act_")
        status = "proposed" if scope_allowed else "blocked_by_scope"
        self.db.execute(
            """
            INSERT INTO actions
                (id, engagement_id, phase, target, port, action_type, command, risk,
                 expected_evidence, status, scope_allowed, scope_reason, approval_required, created_at)
            VALUES
                (:id, :engagement, :phase, :target, :port, :type, :command, :risk,
                 :evidence, :status, :allowed, :reason, :approval, :created)
            """,
            {
                "id": action_id,
                "engagement": engagement_id,
                "phase": phase,
                "target": target,
                "port": port,
                "type": action_type,
                "command": command,
                "risk": risk,
                "evidence": expected_evidence,
                "status": status,
                "allowed": int(scope_allowed),
                "reason": scope_reason,
                "approval": int(approval_required),
                "created": utcnow(),
            },
        )
        return self.get_action(action_id) or {}

    def get_action(self, action_id: str) -> dict[str, Any] | None:
        row = self.db.fetch_one("SELECT * FROM actions WHERE id = :id", {"id": action_id})
        return _normalise_action(row) if row else None

    def list_actions(self, engagement_id: str) -> list[dict[str, Any]]:
        rows = self.db.fetch_all(
            "SELECT * FROM actions WHERE engagement_id = :id ORDER BY created_at, id",
            {"id": engagement_id},
        )
        return [_normalise_action(row) for row in rows]

    def update_action(self, action_id: str, **fields: Any) -> None:
        allowed = {"status", "approved_by", "approved_at"}
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            return
        assignments = ", ".join(f"{key} = :{key}" for key in updates)
        updates["action_id"] = action_id
        self.db.execute(f"UPDATE actions SET {assignments} WHERE id = :action_id", updates)

    def add_finding(
        self,
        engagement_id: str,
        title: str,
        owasp_ref: str,
        cvss_vector: str,
        evidence: str,
        remediation: str,
        verified_by_human: bool,
    ) -> dict[str, Any]:
        finding_id = new_id("find_")
        self.db.execute(
            """
            INSERT INTO findings
                (id, engagement_id, title, owasp_ref, cvss_vector, evidence, remediation,
                 verified_by_human, created_at)
            VALUES
                (:id, :engagement, :title, :owasp, :cvss, :evidence, :remediation, :verified, :created)
            """,
            {
                "id": finding_id,
                "engagement": engagement_id,
                "title": title,
                "owasp": owasp_ref,
                "cvss": cvss_vector,
                "evidence": evidence,
                "remediation": remediation,
                "verified": int(verified_by_human),
                "created": utcnow(),
            },
        )
        return self.db.fetch_one("SELECT * FROM findings WHERE id = :id", {"id": finding_id}) or {}

    def list_findings(self, engagement_id: str) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            "SELECT * FROM findings WHERE engagement_id = :id ORDER BY created_at, id",
            {"id": engagement_id},
        )

    # ---------- Audit ----------

    def audit(self, engagement_id: str, actor: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        payload_json = jdumps(payload)
        created = utcnow()
        event_id = new_id("evt_")
        with self.db.connection() as conn:
            row = conn.execute(
                text("SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq FROM audit_events")
            ).mappings().one()
            seq = int(row["next_seq"])
            previous = conn.execute(
                text("SELECT hash FROM audit_events WHERE seq = :seq"),
                {"seq": seq - 1} if seq > 1 else {"seq": 0},
            ).mappings().first()
            prev_hash = str(previous["hash"]) if previous else ""
            material = f"{prev_hash}|{created}|{engagement_id}|{actor}|{event_type}|{payload_json}"
            digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
            conn.execute(
                text(
                    """
                    INSERT INTO audit_events
                        (seq, id, engagement_id, actor, event_type, payload_json, prev_hash, hash, created_at)
                    VALUES
                        (:seq, :id, :engagement, :actor, :type, :payload, :prev, :hash, :created)
                    """
                ),
                {
                    "seq": seq,
                    "id": event_id,
                    "engagement": engagement_id,
                    "actor": actor,
                    "type": event_type,
                    "payload": payload_json,
                    "prev": prev_hash,
                    "hash": digest,
                    "created": created,
                },
            )
        return {
            "seq": seq,
            "id": event_id,
            "engagement_id": engagement_id,
            "actor": actor,
            "event_type": event_type,
            "payload": payload,
            "prev_hash": prev_hash,
            "hash": digest,
            "created_at": created,
        }

    def list_audit(self, engagement_id: str) -> list[dict[str, Any]]:
        rows = self.db.fetch_all(
            "SELECT * FROM audit_events WHERE engagement_id = :id ORDER BY seq",
            {"id": engagement_id},
        )
        for row in rows:
            row["payload"] = jloads(row.pop("payload_json"), {})
        return rows

    def verify_audit_chain(self, engagement_id: str | None = None) -> tuple[bool, list[str]]:
        if engagement_id:
            rows = self.db.fetch_all(
                "SELECT * FROM audit_events WHERE engagement_id = :id ORDER BY seq",
                {"id": engagement_id},
            )
        else:
            rows = self.db.fetch_all("SELECT * FROM audit_events ORDER BY seq")
        errors: list[str] = []
        expected_prev = str(rows[0]["prev_hash"]) if rows else ""
        for index, row in enumerate(rows):
            payload_json = row["payload_json"]
            material = (
                f"{row['prev_hash']}|{row['created_at']}|{row['engagement_id']}|"
                f"{row['actor']}|{row['event_type']}|{payload_json}"
            )
            expected = hashlib.sha256(material.encode("utf-8")).hexdigest()
            if index > 0 and row["prev_hash"] != expected_prev:
                errors.append(f"seq {row['seq']}: prev_hash mismatch")
            if row["hash"] != expected:
                errors.append(f"seq {row['seq']}: hash mismatch")
            expected_prev = row["hash"]
        return (not errors, errors)
