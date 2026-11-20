"""Application-Service fuer Sentinel: RoE, Scope, Freigaben und Audit."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from typing import Any

from ..config import Settings
from ..debate.report import build_engagement_report
from ..i18n import normalize_lang
from ..llm.base import LLMClient
from ..storage import Repository
from .planner import build_llm_plan, build_rule_plan
from .scope import ScopeError, ScopeGuard, normalize_scope


class EngagementNotFound(RuntimeError):
    pass


class EngagementError(RuntimeError):
    pass


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise EngagementError(f"{field} muss ein Datum im Format YYYY-MM-DD sein.") from None


def _assert_valid_window(engagement: dict[str, Any]) -> None:
    today = date.today()
    start = _parse_date(str(engagement["valid_from"]), "valid_from")
    end = _parse_date(str(engagement["valid_until"]), "valid_until")
    if start > end:
        raise EngagementError("valid_from liegt nach valid_until.")
    if today < start:
        raise EngagementError("Das Engagement ist noch nicht gueltig.")
    if today > end:
        raise EngagementError("Das Engagement ist abgelaufen.")


def create_engagement(
    repo: Repository,
    settings: Settings,
    *,
    client_name: str,
    scope: list[str],
    ports: list[int],
    valid_from: str,
    valid_until: str,
    roe_text: str,
    authorized_by: str,
    emergency_contact: str,
    tenant_id: str = "default",
) -> dict[str, Any]:
    if not client_name.strip():
        raise EngagementError("Auftraggeber fehlt.")
    if len(roe_text.strip()) < 50:
        raise EngagementError("Die RoE ist zu kurz. Dokumentiere Freigabe, Scope und Notfallkontakte.")
    if not authorized_by.strip() or not emergency_contact.strip():
        raise EngagementError("Freigabeinstanz und Notfallkontakt sind Pflicht.")
    start = _parse_date(valid_from, "valid_from")
    end = _parse_date(valid_until, "valid_until")
    if start > end:
        raise EngagementError("valid_from liegt nach valid_until.")
    if end < date.today():
        raise EngagementError("valid_until liegt in der Vergangenheit.")
    clean_ports = sorted({int(port) for port in ports if str(port).strip()})
    if not clean_ports:
        raise EngagementError("Mindestens ein Port muss freigegeben sein.")
    try:
        clean_scope = normalize_scope(scope, clean_ports, settings.allow_public_targets)
    except ScopeError as exc:
        raise EngagementError(str(exc)) from None
    roe_hash = hashlib.sha256(roe_text.encode("utf-8")).hexdigest()
    engagement = repo.create_engagement(
        client_name=client_name.strip(),
        roe_text=roe_text.strip(),
        roe_hash=roe_hash,
        scope=clean_scope,
        ports=clean_ports,
        authorized_by=authorized_by.strip(),
        emergency_contact=emergency_contact.strip(),
        valid_from=start.isoformat(),
        valid_until=end.isoformat(),
        tenant_id=tenant_id,
    )
    repo.audit(
        engagement["id"],
        actor="system",
        event_type="engagement.created",
        payload={
            "client_name": client_name.strip(),
            "scope": clean_scope,
            "ports": clean_ports,
            "valid_from": start.isoformat(),
            "valid_until": end.isoformat(),
            "roe_hash": roe_hash,
            "authorized_by": authorized_by.strip(),
        },
    )
    return repo.get_engagement(engagement["id"]) or engagement


def get_guard(engagement: dict[str, Any], settings: Settings) -> ScopeGuard:
    try:
        return ScopeGuard(
            [str(entry) for entry in engagement.get("scope", [])],
            [int(port) for port in engagement.get("ports", [])],
            allow_public_targets=settings.allow_public_targets,
        )
    except ScopeError as exc:
        raise EngagementError(f"Gespeicherter Scope ist ungueltig: {exc}") from None


def generate_plan(
    repo: Repository,
    settings: Settings,
    client: LLMClient,
    engagement_id: str,
    *,
    mode: str = "rules",
    lang: str = "de",
) -> list[dict[str, Any]]:
    engagement = repo.get_engagement(engagement_id)
    if not engagement:
        raise EngagementNotFound(engagement_id)
    if engagement.get("kill_switch"):
        raise EngagementError("Kill-Switch aktiv. Keine neuen Aktionen.")
    _assert_valid_window(engagement)
    guard = get_guard(engagement, settings)
    fallback_reason = ""
    actions: list[dict[str, Any]] = []
    if mode == "llm" and not settings.is_mock:
        try:
            actions = build_llm_plan(engagement, guard, client, settings, normalize_lang(lang))
        except Exception as exc:
            fallback_reason = f"{type(exc).__name__}: {str(exc)[:200]}"
            actions = build_rule_plan(engagement, guard)
    else:
        actions = build_rule_plan(engagement, guard)
    if fallback_reason:
        repo.audit(
            engagement_id,
            actor="system",
            event_type="plan.llm_failed_fallback_rules",
            payload={"reason": fallback_reason},
        )
    created: list[dict[str, Any]] = []
    for action in actions:
        stored = repo.add_action(
            engagement_id=engagement_id,
            phase=str(action.get("phase", "")),
            target=str(action.get("target", "")),
            port=int(action.get("port", 443)),
            action_type=str(action.get("action_type", "READ_ONLY")),
            command=str(action.get("command", "")),
            risk=str(action.get("risk", "low")),
            expected_evidence=str(action.get("expected_evidence", "")),
            scope_allowed=bool(action.get("scope_allowed")),
            scope_reason=str(action.get("scope_reason", "")),
            approval_required=str(action.get("action_type")) == "ACTIVE_REQUIRES_APPROVAL",
        )
        created.append(stored)
        repo.audit(
            engagement_id,
            actor="system",
            event_type="action.proposed" if stored.get("scope_allowed") else "action.blocked_by_scope",
            payload={
                "action_id": stored["id"],
                "target": stored["target"],
                "port": stored["port"],
                "action_type": stored["action_type"],
                "status": stored["status"],
                "scope_reason": stored["scope_reason"],
            },
        )
    return created


def approve_action(
    repo: Repository,
    settings: Settings,
    action_id: str,
    approver: str,
) -> dict[str, Any]:
    action = repo.get_action(action_id)
    if not action:
        raise EngagementNotFound(action_id)
    engagement = repo.get_engagement(str(action["engagement_id"]))
    if not engagement:
        raise EngagementNotFound(str(action["engagement_id"]))
    if engagement.get("kill_switch"):
        raise EngagementError("Kill-Switch aktiv.")
    _assert_valid_window(engagement)
    if not action.get("scope_allowed"):
        raise EngagementError("Aktion ist durch den Scope blockiert und kann nicht freigegeben werden.")
    if action.get("status") != "proposed":
        raise EngagementError(f"Aktion ist nicht im Status 'proposed' (aktuell: {action.get('status')}).")
    if not action.get("approval_required"):
        raise EngagementError("Read-only-Aktionen brauchen keine Freigabe; sie werden nicht ausgefuehrt.")
    if not approver.strip():
        raise EngagementError("Name der freigebenden Person fehlt.")
    repo.update_action(
        action_id,
        status="approved",
        approved_by=approver.strip(),
        approved_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
    )
    repo.audit(
        str(action["engagement_id"]),
        actor=approver.strip(),
        event_type="action.approved",
        payload={
            "action_id": action_id,
            "target": action["target"],
            "port": action["port"],
            "command": action["command"],
        },
    )
    return repo.get_action(action_id) or action


def reject_action(repo: Repository, action_id: str, actor: str, reason: str = "") -> dict[str, Any]:
    action = repo.get_action(action_id)
    if not action:
        raise EngagementNotFound(action_id)
    if action.get("status") not in {"proposed", "approved"}:
        raise EngagementError(f"Aktion kann nicht abgelehnt werden (Status: {action.get('status')}).")
    repo.update_action(action_id, status="rejected")
    repo.audit(
        str(action["engagement_id"]),
        actor=actor or "human",
        event_type="action.rejected",
        payload={"action_id": action_id, "reason": reason[:500]},
    )
    return repo.get_action(action_id) or action


def activate_kill_switch(repo: Repository, engagement_id: str, actor: str) -> dict[str, Any]:
    engagement = repo.get_engagement(engagement_id)
    if not engagement:
        raise EngagementNotFound(engagement_id)
    repo.set_kill_switch(engagement_id, True)
    repo.audit(
        engagement_id,
        actor=actor or "human",
        event_type="engagement.kill_switch",
        payload={"active": True},
    )
    return repo.get_engagement(engagement_id) or engagement


def add_finding(
    repo: Repository,
    engagement_id: str,
    *,
    title: str,
    owasp_ref: str,
    cvss_vector: str,
    evidence: str,
    remediation: str,
    verified_by_human: bool,
    actor: str,
) -> dict[str, Any]:
    if not verified_by_human:
        raise EngagementError("Findings duerfen nur menschlich verifiziert gespeichert werden.")
    if not title.strip() or not evidence.strip() or not remediation.strip():
        raise EngagementError("Titel, Evidenz und Remediation sind Pflicht.")
    engagement = repo.get_engagement(engagement_id)
    if not engagement:
        raise EngagementNotFound(engagement_id)
    finding = repo.add_finding(
        engagement_id,
        title=title.strip(),
        owasp_ref=owasp_ref.strip(),
        cvss_vector=cvss_vector.strip(),
        evidence=evidence.strip(),
        remediation=remediation.strip(),
        verified_by_human=True,
    )
    repo.audit(
        engagement_id,
        actor=actor or "human",
        event_type="finding.verified",
        payload={"finding_id": finding["id"], "title": title.strip(), "owasp_ref": owasp_ref.strip()},
    )
    return finding


def engagement_report(repo: Repository, settings: Settings, engagement_id: str, lang: str) -> str:
    engagement = repo.get_engagement(engagement_id)
    if not engagement:
        raise EngagementNotFound(engagement_id)
    return build_engagement_report(
        engagement=engagement,
        findings=engagement.get("findings", []),
        lang=normalize_lang(lang),
        execution_enabled=settings.pentest_execution_enabled,
    )
