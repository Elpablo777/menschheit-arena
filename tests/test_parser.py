from __future__ import annotations

import pytest

from menschheit.debate.parser import LLMOutputError, extract_json, parse_judge, parse_moderator, parse_turn


def test_extract_json_from_fence() -> None:
    text = 'Hier ist das Ergebnis:\n```json\n{"a": 1}\n```\nEnde.'
    assert extract_json(text) == {"a": 1}


def test_extract_json_with_trailing_comma() -> None:
    assert extract_json('{"a": 1, "b": [1, 2,],}') == {"a": 1, "b": [1, 2]}


def test_turn_aliases_are_normalised() -> None:
    turn = parse_turn(
        '{"argument": "These", "confidence": "72", "steelman": "Gegenpunkt", '
        '"concessions": ["Risiko"], "falsification": "Bedingung"}'
    )
    assert turn.public_argument == "These"
    assert turn.confidence_own_thesis == 72
    assert turn.steelman_opponent == "Gegenpunkt"
    assert turn.conceded_claims == ["Risiko"]
    assert turn.falsification_condition == "Bedingung"


def test_turn_rejects_empty_public_argument() -> None:
    with pytest.raises(LLMOutputError):
        parse_turn('{"public_argument": "   "}')


def test_moderator_normalises_decision() -> None:
    verdict = parse_moderator('{"decision": "continue refine", "round_summary": "x"}')
    assert verdict.decision == "CONTINUE_REFINE"
    verdict = parse_moderator('{"decision": "unknown"}')
    assert verdict.decision == "CONTINUE_REFINE"


def test_judge_recomputes_totals() -> None:
    verdict = parse_judge(
        """
        {
          "winner": "pro",
          "scores": {
            "pro": {"claims": 8, "logic": 9, "qualifiers": 7, "rebuttals": 8, "realism": 8, "total": 1},
            "contra": {"claims": 7, "logic": 7, "qualifiers": 7, "rebuttals": 7, "realism": 7, "total": 99}
          }
        }
        """
    )
    assert verdict.pro_score().total == 40
    assert verdict.contra_score().total == 35
    assert verdict.winner == "pro"


def test_invalid_json_raises() -> None:
    with pytest.raises(LLMOutputError):
        extract_json("kein json")
