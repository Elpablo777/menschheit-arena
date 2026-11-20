"""Robustes Parsen von LLM-JSON ohne Code-Ausfuehrung."""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from .models import JudgeVerdict, ModeratorVerdict, TurnPayload

T = TypeVar("T", bound=BaseModel)


class LLMOutputError(RuntimeError):
    pass


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise LLMOutputError("Leere LLM-Antwort.")
    fence = _FENCE.search(raw)
    if fence:
        raw = fence.group(1).strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise LLMOutputError("LLM-Antwort enthaelt kein JSON-Objekt.") from None
        candidate = _TRAILING_COMMA.sub(r"\1", raw[start : end + 1])
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError as exc:
            snippet = raw[max(0, start) : min(len(raw), start + 240)].replace("\n", " ")
            raise LLMOutputError(f"Ungueltiges JSON: {exc.msg} bei Position {exc.pos}: {snippet}") from None
    if not isinstance(value, dict):
        raise LLMOutputError("LLM-JSON ist kein Objekt.")
    return value


def _normalise_turn(data: dict[str, Any]) -> dict[str, Any]:
    normalised = dict(data)
    if "steelman_opponent" not in normalised:
        for alias in ("steelman", "opponent_steelman", "strongest_opponent_argument"):
            if alias in normalised:
                normalised["steelman_opponent"] = normalised[alias]
                break
    if "public_argument" not in normalised:
        for alias in ("argument", "public", "response", "answer"):
            if alias in normalised:
                normalised["public_argument"] = normalised[alias]
                break
    if "confidence_own_thesis" not in normalised:
        for alias in ("confidence", "confidence_score", "own_confidence"):
            if alias in normalised:
                normalised["confidence_own_thesis"] = normalised[alias]
                break
    if "conceded_claims" not in normalised:
        for alias in ("concessions", "conceded", "conceded_points"):
            if alias in normalised:
                normalised["conceded_claims"] = normalised[alias]
                break
    if "falsification_condition" not in normalised:
        for alias in ("falsification", "falsification_criterion"):
            if alias in normalised:
                normalised["falsification_condition"] = normalised[alias]
                break
    if "internal_reasoning" not in normalised:
        for alias in ("private_reasoning", "reasoning", "scratchpad"):
            if alias in normalised:
                normalised["internal_reasoning"] = normalised[alias]
                break
    return normalised


def parse_turn(text: str) -> TurnPayload:
    try:
        return TurnPayload.model_validate(_normalise_turn(extract_json(text)))
    except (ValidationError, LLMOutputError) as exc:
        raise LLMOutputError(f"Turn-Validierung fehlgeschlagen: {exc}") from None


def parse_moderator(text: str) -> ModeratorVerdict:
    try:
        return ModeratorVerdict.model_validate(extract_json(text))
    except (ValidationError, LLMOutputError) as exc:
        raise LLMOutputError(f"Moderator-Validierung fehlgeschlagen: {exc}") from None


def parse_judge(text: str) -> JudgeVerdict:
    try:
        verdict = JudgeVerdict.model_validate(extract_json(text))
    except (ValidationError, LLMOutputError) as exc:
        raise LLMOutputError(f"Richter-Validierung fehlgeschlagen: {exc}") from None
    for block in verdict.scores.values():
        block.total = block.computed_total()
    return verdict
