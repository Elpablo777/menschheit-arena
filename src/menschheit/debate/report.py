"""Markdown-Berichte fuer Arena und Sentinel."""

from __future__ import annotations

import re
from typing import Any, Iterable

from ..i18n import t

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def clean(text: object) -> str:
    """Entfernt Steuerzeichen und entschaerft HTML-Tags in LLM-Text."""
    value = _CONTROL.sub("", str(text or ""))
    value = value.replace("<", "\u2039").replace(">", "\u203a")
    return value.strip()


def cell(text: object) -> str:
    return clean(text).replace("|", "\\|").replace("\n", " ")


def _bullets(items: Iterable[str], empty: str) -> str:
    values = [clean(item) for item in items if clean(item)]
    if not values:
        return f"- {empty}"
    return "\n".join(f"- {value}" for value in values)


def _surviving(items: list[dict[str, Any]], empty: str) -> str:
    if not items:
        return f"- {empty}"
    lines: list[str] = []
    for item in items:
        claim = clean(item.get("claim", ""))
        why = clean(item.get("why", ""))
        lines.append(f"- **{claim}**" + (f" – {why}" if why else ""))
    return "\n".join(lines)


def _refuted(items: list[dict[str, Any]], empty: str) -> str:
    if not items:
        return f"- {empty}"
    lines: list[str] = []
    for item in items:
        side = str(item.get("side", "")).lower()
        claim = clean(item.get("claim", ""))
        why = clean(item.get("why", ""))
        lines.append(f"- **{side.upper()}:** {claim}" + (f" – {why}" if why else ""))
    return "\n".join(lines)


def _score_line(label: str, block: dict[str, Any]) -> str:
    return (
        f"| {label} | {block.get('claims', 0)} | {block.get('logic', 0)} | "
        f"{block.get('qualifiers', 0)} | {block.get('rebuttals', 0)} | "
        f"{block.get('realism', 0)} | **{block.get('total', 0)}/50** |"
    )


def winner_label(winner: str, lang: str) -> str:
    if winner == "pro":
        return "Pro Menschheit" if lang == "de" else "Pro humanity"
    if winner == "contra":
        return "Contra / Skeptiker" if lang == "de" else "Contra / sceptic"
    return t("report.draw", lang)


def build_debate_report(
    *,
    debate: dict[str, Any],
    turns: list[dict[str, Any]],
    moderations: list[dict[str, Any]],
    pass_ab: dict[str, Any],
    pass_ba: dict[str, Any],
    bias_delta: float,
    final_scores: dict[str, dict[str, Any]],
    winner: str,
    lang: str,
    is_mock: bool,
) -> str:
    topic = clean(debate.get("topic", ""))
    created = clean(debate.get("created_at", ""))
    stop_reason = clean(debate.get("stop_reason", ""))
    models = debate.get("models", {}) or {}
    rounds = len({turn.get("round_no") for turn in turns})
    lines: list[str] = [
        f"# {t('report.title', lang)}: {topic}",
        "",
        f"> {t('report.generated', lang)}: {created} · {t('report.disclaimer', lang)}",
        "",
        f"## 1. {t('report.executive', lang)}",
        "",
        clean(pass_ab.get("summary") or pass_ba.get("summary") or ""),
        "",
        f"**{t('report.winner', lang)}:** {winner_label(winner, lang)}  ",
        f"**{t('report.bias_delta', lang)}:** {bias_delta:.1f}  ",
        f"**{t('report.rounds', lang)}:** {rounds}  ",
        f"**{t('report.stop_reason', lang)}:** {stop_reason}",
        "",
        f"| {t('report.side', lang)} | Claims | Logic | Qualifiers | Rebuttals | Realism | Total |",
        "|---|---:|---:|---:|---:|---:|---:|",
        _score_line("Pro", final_scores.get("pro", {})),
        _score_line("Contra", final_scores.get("contra", {})),
        "",
        f"## 2. {t('report.pro', lang)}",
        "",
        _surviving(pass_ab.get("pro_surviving", []), t("common.none", lang)),
        "",
        f"## 3. {t('report.contra', lang)}",
        "",
        _surviving(pass_ab.get("contra_surviving", []), t("common.none", lang)),
        "",
        f"## 4. {t('report.refuted', lang)}",
        "",
        _refuted(pass_ab.get("refuted", []), t("common.none", lang)),
        "",
        f"## 5. {t('report.conflicts', lang)}",
        "",
        _bullets(pass_ab.get("open_conflicts", []), t("common.none", lang)),
        "",
        f"## 6. {t('report.rules', lang)}",
        "",
        _bullets(pass_ab.get("architecture_rules", []), t("common.none", lang)),
        "",
        f"## 7. {t('report.transparency', lang)}",
        "",
        f"- **{t('report.models', lang)}:** Pro=`{clean(models.get('pro', ''))}`, "
        f"Contra=`{clean(models.get('contra', ''))}`, Judge=`{clean(models.get('judge', ''))}`, "
        f"Moderator=`{clean(models.get('moderator', ''))}`",
        f"- **{t('report.mode', lang)}:** {t('report.mode_mock', lang) if is_mock else t('report.mode_live', lang)}",
        f"- **{t('report.language', lang)}:** {lang}",
        f"- **{t('report.method', lang)}:** {t('report.method_value', lang)}",
        f"- **{t('report.bias', lang)}:** "
        f"{t('report.bias_high', lang) if bias_delta >= 4 else t('report.bias_low', lang)} "
        f"({'passes' if lang == 'en' else 'Durchlauf'} A/B {'and' if lang == 'en' else 'und'} B/A, "
        f"{'delta' if lang == 'en' else 'Delta'} {bias_delta:.1f}).",
        "",
        f"### {t('report.appendix', lang)}",
        "",
    ]
    for turn in turns:
        is_pro = turn.get("role") == "pro"
        if lang == "en":
            role = "Pro humanity" if is_pro else "Contra / sceptic"
        else:
            role = "Pro Menschheit" if is_pro else "Contra / Skeptiker"
        lines.extend(
            [
                f"#### {t('arena.round', lang)} {turn.get('round_no')} – {role}",
                "",
                f"**{t('arena.steelman', lang)}:** {clean(turn.get('steelman', ''))}",
                "",
                clean(turn.get("public_argument", "")),
                "",
                f"*{t('arena.confidence', lang)}:* {turn.get('confidence', 0)} · "
                f"*{t('arena.falsification', lang)}:* {clean(turn.get('falsification', ''))}",
                "",
            ]
        )
        for moderation in moderations:
            if moderation.get("round_no") == turn.get("round_no") and turn.get("role") == "contra":
                lines.extend(
                    [
                        f"> **{t('arena.moderator', lang)}:** "
                        f"{clean(moderation.get('summary', ''))} "
                        f"({clean(moderation.get('decision', ''))})",
                        "",
                    ]
                )
    lines.extend(
        [
            "---",
            "",
            f"*{t('report.disclaimer', lang)}*",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def build_engagement_report(
    *,
    engagement: dict[str, Any],
    findings: list[dict[str, Any]],
    lang: str,
    execution_enabled: bool,
) -> str:
    client = clean(engagement.get("client_name", ""))
    eng_id = clean(engagement.get("id", ""))
    scope = engagement.get("scope", []) or []
    actions = engagement.get("actions", []) or []
    audit = engagement.get("audit", []) or []
    kill_switch = bool(engagement.get("kill_switch"))
    verified = [item for item in findings if item.get("verified_by_human")]
    lines: list[str] = [
        f"# {t('sentinel.report', lang)}: {client}",
        "",
        f"> {t('report.generated', lang)} · {t('report.disclaimer', lang)}",
        "",
        f"## {t('report.engagement', lang)}",
        "",
        f"- **ID:** `{eng_id}`",
        f"- **{t('sentinel.form.client', lang)}:** {client}",
        f"- **{t('sentinel.form.authorized_by', lang)}:** {clean(engagement.get('authorized_by', ''))}",
        f"- **{t('sentinel.form.emergency', lang)}:** {clean(engagement.get('emergency_contact', ''))}",
        f"- **{t('report.validity', lang)}:** {clean(engagement.get('valid_from', ''))} – "
        f"{clean(engagement.get('valid_until', ''))}",
        f"- **{t('report.roe_hash', lang)}:** `{clean(engagement.get('roe_hash', ''))}`",
        f"- **{t('sentinel.detail.kill', lang)}:** {t('common.yes', lang) if kill_switch else t('common.no', lang)}",
        "",
        f"## {t('report.scope', lang)}",
        "",
    ]
    if scope:
        lines.extend(f"- `{clean(item)}`" for item in scope)
    else:
        lines.append(f"- {t('common.none', lang)}")
    lines.extend(
        [
            "",
            f"## {t('report.actions', lang)}",
            "",
            "| Phase | Target | Port | Type | Status | Scope | Approval |",
            "|---|---|---:|---|---|---|---|",
        ]
    )
    for action in actions:
        lines.append(
            "| {phase} | `{target}` | {port} | {type} | {status} | {scope} | {approval} |".format(
                phase=cell(action.get("phase", "")),
                target=cell(action.get("target", "")),
                port=action.get("port", ""),
                type=cell(action.get("action_type", "")),
                status=cell(action.get("status", "")),
                scope="OK" if action.get("scope_allowed") else "BLOCKED",
                approval=cell(action.get("approved_by") or "-"),
            )
        )
    lines.extend(
        [
            "",
            f"## {t('report.verified_findings', lang)}",
            "",
        ]
    )
    if verified:
        for finding in verified:
            lines.extend(
                [
                    f"### {clean(finding.get('title', ''))}",
                    "",
                    f"- **OWASP:** {clean(finding.get('owasp_ref', '')) or '-'}",
                    f"- **CVSS v4.0:** `{clean(finding.get('cvss_vector', '')) or '-'}`",
                    "",
                    f"**{t('report.evidence', lang)}:** {clean(finding.get('evidence', ''))}",
                    "",
                    f"**{t('report.remediation', lang)}:** {clean(finding.get('remediation', ''))}",
                    "",
                ]
            )
    else:
        lines.extend([f"- {t('sentinel.findings.empty', lang)}", ""])
    lines.extend(
        [
            f"## {t('report.audit', lang)}",
            "",
            f"- **{t('report.events', lang)}:** {len(audit)}",
            f"- **{t('report.chain_valid', lang)}:** {t('common.yes', lang) if engagement.get('audit_valid') else t('common.no', lang)}",
            f"- **{t('system.execution', lang)}:** "
            f"{t('common.yes', lang) if execution_enabled else t('common.no', lang)}",
            "",
            f"> {t('report.no_active_execution', lang)}",
            "",
            "---",
            "",
            f"*{t('report.disclaimer', lang)}*",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"
