"""Laden und Rendern der versionierten Prompt-Dateien."""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

from ..i18n import normalize_lang


@lru_cache(maxsize=32)
def load_prompt(name: str, lang: str) -> str:
    lang = normalize_lang(lang)
    path = resources.files("menschheit.prompts").joinpath(lang, f"{name}.md")
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=8)
def load_knowledge(lang: str) -> str:
    lang = normalize_lang(lang)
    path = resources.files("menschheit.knowledge").joinpath(f"base.{lang}.md")
    return path.read_text(encoding="utf-8")


def render(template: str, **values: object) -> str:
    result = template
    for key, value in values.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result


def turn_messages(
    role: str,
    lang: str,
    topic: str,
    round_no: int,
    rounds_requested: int,
    opponent: str,
    own_previous: str,
    directive: str,
    word_limit: int,
    knowledge: str,
) -> list[dict[str, str]]:
    system = render(
        load_prompt(role, lang),
        word_limit=word_limit,
        language=lang,
    )
    if lang == "en":
        user = (
            f"## Debate topic\n{topic}\n\n"
            f"## Context\nLanguage: English\nRound: {round_no} of {rounds_requested}\n\n"
            f"## Your previous public argument\n{own_previous or '(none)'}\n\n"
            f"## Last anonymised public argument from the opponent\n{opponent or '(none - this is the isolated opening position)'}\n\n"
            f"## Moderator directive\n{directive or '(none)'}\n\n"
            f"## Neutral knowledge base\n{knowledge}\n\n"
            "Return only the JSON object required by the system prompt."
        )
    else:
        user = (
            f"## Debattenthema\n{topic}\n\n"
            f"## Kontext\nSprache: Deutsch\nRunde: {round_no} von {rounds_requested}\n\n"
            f"## Dein bisheriger öffentlicher Beitrag\n{own_previous or '(keiner)'}\n\n"
            f"## Letzter anonymisierter öffentlicher Beitrag des Gegners\n{opponent or '(keiner - dies ist die isolierte Erstposition)'}\n\n"
            f"## Moderator-Direktive\n{directive or '(keine)'}\n\n"
            f"## Neutrale Wissensbasis\n{knowledge}\n\n"
            "Antworte ausschließlich mit dem im System-Prompt geforderten JSON-Objekt."
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def moderator_messages(
    lang: str,
    topic: str,
    round_no: int,
    rounds_requested: int,
    round_public: list[dict[str, object]],
    previous_directive: str,
) -> list[dict[str, str]]:
    system = load_prompt("moderator", lang)
    lines: list[str] = []
    for item in round_public:
        if lang == "en":
            lines.append(
                f"- {item['role']}: confidence={item['confidence']}; "
                f"steelman={item['steelman']}; public={item['public_argument']}; "
                f"conceded={item['conceded_claims']}; falsification={item['falsification']}"
            )
        else:
            lines.append(
                f"- {item['role']}: Konfidenz={item['confidence']}; "
                f"Steelman={item['steelman']}; öffentlich={item['public_argument']}; "
                f"zugestanden={item['conceded_claims']}; Falsifikation={item['falsification']}"
            )
    if lang == "en":
        user = (
            f"Topic: {topic}\nRound: {round_no} of {rounds_requested}\n"
            f"Previous directive: {previous_directive or '(none)'}\n\n"
            "Current round (anonymised):\n" + "\n".join(lines) + "\n\n"
            "Return only the JSON object required by the system prompt."
        )
    else:
        user = (
            f"Thema: {topic}\nRunde: {round_no} von {rounds_requested}\n"
            f"Bisherige Direktive: {previous_directive or '(keine)'}\n\n"
            "Aktuelle Runde (anonymisiert):\n" + "\n".join(lines) + "\n\n"
            "Antworte ausschließlich mit dem im System-Prompt geforderten JSON-Objekt."
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def planner_messages(
    lang: str,
    scope: list[str],
    ports: list[int],
    phase_note: str = "",
) -> list[dict[str, str]]:
    system = load_prompt("planner", lang)
    scope_text = "\n".join(f"- {entry}" for entry in scope)
    if lang == "en":
        user = (
            "Authorised scope (the only targets you may propose):\n"
            f"{scope_text}\n\nAllowed ports: {', '.join(str(port) for port in ports)}\n"
            f"Phase note: {phase_note or '(none)'}\n\n"
            "Propose a small, verifiable plan. Do not claim that anything was executed. "
            "Return only the JSON object required by the system prompt."
        )
    else:
        user = (
            "Freigegebener Scope (nur diese Ziele darfst du vorschlagen):\n"
            f"{scope_text}\n\nErlaubte Ports: {', '.join(str(port) for port in ports)}\n"
            f"Phasen-Hinweis: {phase_note or '(keiner)'}\n\n"
            "Schlage einen kleinen, prüfbaren Plan vor. Behaupte nicht, dass etwas ausgeführt wurde. "
            "Antworte ausschließlich mit dem im System-Prompt geforderten JSON-Objekt."
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def judge_messages(
    lang: str,
    topic: str,
    order: str,
    transcript: str,
    bias_note: str = "",
) -> list[dict[str, str]]:
    system = load_prompt("judge", lang)
    mapping = "A = Pro, B = Contra" if order == "ab" else "A = Contra, B = Pro"
    if lang == "en":
        user = (
            f"Topic: {topic}\nJudging pass: {order.upper()} (order of positions: {mapping})\n"
            f"{bias_note}\n\nTranscript:\n{transcript}\n\n"
            "Return only the JSON object required by the system prompt. Score pro and contra explicitly."
        )
    else:
        user = (
            f"Thema: {topic}\nRichter-Durchlauf: {order.upper()} (Reihenfolge der Positionen: {mapping})\n"
            f"{bias_note}\n\nTranskript:\n{transcript}\n\n"
            "Antworte ausschließlich mit dem im System-Prompt geforderten JSON-Objekt. Bewerte Pro und Contra explizit."
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
