"""Deterministischer und optional LLM-gestuetzter Pentest-Planer.

Wichtig: Der Planer fuehrt nichts aus. Er erzeugt Vorschlaege, die anschliessend
gegen den Scope geprueft und fuer aktive Schritte menschlich freigegeben werden.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from ..config import Settings
from ..debate.models import PlannerAction, PlannerOutput
from ..debate.parser import LLMOutputError, extract_json
from ..debate.prompts import planner_messages
from ..i18n import normalize_lang
from ..llm import model_for
from ..llm.base import LLMClient
from .scope import ScopeDecision, ScopeGuard, parse_target

MAX_ACTIONS = 24


def _url_for(target: str, port: int) -> str:
    parsed = urlparse(target)
    if parsed.scheme in {"http", "https"}:
        return target
    host = target.strip()
    if ":" in host and host.count(":") == 1 and not host.startswith("["):
        host = host.rsplit(":", 1)[0]
    scheme = "https" if port == 443 else "http"
    if ":" in host and not host.startswith("[") and host.count(":") > 1:
        host = f"[{host}]"
    return f"{scheme}://{host}:{port}"


def _shell_target(target: str, port: int) -> str:
    parsed = urlparse(target)
    if parsed.hostname:
        return parsed.hostname
    if ":" in target and target.count(":") == 1 and target.rsplit(":", 1)[1].isdigit():
        return target.rsplit(":", 1)[0]
    return target


def _entry_actions(entry: str, ports: list[int], guard: ScopeGuard) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    parsed = parse_target(entry)
    if parsed.kind == "cidr":
        decision = guard.allows_network(entry)
        actions.append(
            {
                "phase": "BSI-Phase 2: Informationsbeschaffung",
                "target": entry,
                "port": 443,
                "action_type": "ACTIVE_REQUIRES_APPROVAL",
                "command": f"nmap -sn {entry}",
                "risk": "medium",
                "expected_evidence": "Host discovery list; every discovered host must be re-checked against the scope before any further action.",
                "scope_allowed": decision.allowed,
                "scope_reason": decision.reason,
            }
        )
        return actions

    preferred_port = 443 if 443 in ports else (80 if 80 in ports else ports[0])
    host = parsed.host
    scheme_port = parsed.port or preferred_port
    url = _url_for(entry, scheme_port)
    decision: ScopeDecision = guard.check(entry, scheme_port)
    actions.append(
        {
            "phase": "BSI-Phase 2: Informationsbeschaffung",
            "target": url,
            "port": scheme_port,
            "action_type": "READ_ONLY",
            "command": f"curl -sS -D - -o /dev/null --max-time 15 {url}",
            "risk": "low",
            "expected_evidence": "HTTP status, response headers, TLS metadata.",
            "scope_allowed": decision.allowed,
            "scope_reason": decision.reason,
        }
    )
    if scheme_port == 443:
        host_for_tls = host
        actions.append(
            {
                "phase": "BSI-Phase 2: Informationsbeschaffung",
                "target": url,
                "port": 443,
                "action_type": "READ_ONLY",
                "command": f"openssl s_client -connect {host_for_tls}:443 -servername {host_for_tls} </dev/null",
                "risk": "low",
                "expected_evidence": "TLS certificate chain, protocol version, cipher suite.",
                "scope_allowed": decision.allowed,
                "scope_reason": decision.reason,
            }
        )
    host_for_scan = _shell_target(entry, scheme_port)
    port_list = ",".join(str(port) for port in ports)
    scan_decision = guard.check(entry, scheme_port)
    actions.append(
        {
            "phase": "BSI-Phase 4: Aktive Eindringversuche (Vorschlag)",
            "target": url,
            "port": scheme_port,
            "action_type": "ACTIVE_REQUIRES_APPROVAL",
            "command": f"nmap -sV -Pn -p {port_list} {host_for_scan}",
            "risk": "medium",
            "expected_evidence": "Service/version inventory with timestamps; no exploitation is performed.",
            "scope_allowed": scan_decision.allowed,
            "scope_reason": scan_decision.reason,
        }
    )
    return actions


def build_rule_plan(engagement: dict[str, Any], guard: ScopeGuard) -> list[dict[str, Any]]:
    ports = sorted({int(port) for port in engagement.get("ports", [])}) or [80, 443]
    actions: list[dict[str, Any]] = []
    for entry in engagement.get("scope", []):
        actions.extend(_entry_actions(str(entry), ports, guard))
    return _dedupe(actions)[:MAX_ACTIONS]


def _normalise_llm_action(action: PlannerAction, guard: ScopeGuard) -> dict[str, Any]:
    if action.action_type == "READ_ONLY":
        decision = guard.check(action.target, action.port)
    else:
        decision = guard.check(action.target, action.port)
    return {
        "phase": action.phase,
        "target": action.target,
        "port": action.port,
        "action_type": action.action_type,
        "command": action.command,
        "risk": action.risk,
        "expected_evidence": action.expected_evidence,
        "scope_allowed": decision.allowed,
        "scope_reason": decision.reason,
    }


def build_llm_plan(
    engagement: dict[str, Any],
    guard: ScopeGuard,
    client: LLMClient,
    settings: Settings,
    lang: str,
) -> list[dict[str, Any]]:
    messages = planner_messages(
        normalize_lang(lang),
        [str(item) for item in engagement.get("scope", [])],
        [int(port) for port in engagement.get("ports", [])],
    )
    result = client.complete(
        messages,
        model=model_for(settings, "moderator"),
        purpose="planner",
        meta={
            "lang": normalize_lang(lang),
            "targets": [str(item) for item in engagement.get("scope", [])],
        },
    )
    try:
        data = extract_json(result.text)
        output = PlannerOutput.model_validate(data)
    except (LLMOutputError, ValueError) as exc:
        raise LLMOutputError(f"Planer-Ausgabe ungueltig: {exc}") from None
    actions = [_normalise_llm_action(action, guard) for action in output.actions]
    return _dedupe(actions)[:MAX_ACTIONS]


def _dedupe(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, int, str, str]] = set()
    result: list[dict[str, Any]] = []
    for action in actions:
        key = (
            str(action.get("target", "")),
            int(action.get("port", 0)),
            str(action.get("action_type", "")),
            str(action.get("command", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(action)
    return result
