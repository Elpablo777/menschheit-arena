"""Validierte Datenmodelle fuer Debatten, Moderation und Richter."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TurnPayload(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    internal_reasoning: str = ""
    steelman_opponent: str = ""
    public_argument: str = Field(min_length=1)
    confidence_own_thesis: int = Field(default=50, ge=0, le=100)
    conceded_claims: list[str] = Field(default_factory=list)
    falsification_condition: str = ""

    @field_validator("conceded_claims", mode="before")
    @classmethod
    def _coerce_conceded(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        return []

    @field_validator("confidence_own_thesis", mode="before")
    @classmethod
    def _coerce_confidence(cls, value: object) -> int:
        try:
            number = int(float(str(value)))
        except (TypeError, ValueError):
            return 50
        return max(0, min(100, number))

    @field_validator("public_argument", mode="before")
    @classmethod
    def _strip_public(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ModeratorVerdict(BaseModel):
    model_config = ConfigDict(extra="ignore")

    round_summary: str = ""
    sycophancy_detected: bool = False
    drift_detected: bool = False
    decision: Literal["CONTINUE_REFINE", "CONVINCED", "SYNTHESIS_REACHED", "DEADLOCK"] = "CONTINUE_REFINE"
    next_round_directive: str = ""

    @field_validator("decision", mode="before")
    @classmethod
    def _normalise_decision(cls, value: object) -> str:
        raw = str(value or "").strip().upper().replace(" ", "_")
        return raw if raw in {"CONTINUE_REFINE", "CONVINCED", "SYNTHESIS_REACHED", "DEADLOCK"} else "CONTINUE_REFINE"


class ScoreBlock(BaseModel):
    model_config = ConfigDict(extra="ignore")

    claims: int = Field(default=5, ge=0, le=10)
    logic: int = Field(default=5, ge=0, le=10)
    qualifiers: int = Field(default=5, ge=0, le=10)
    rebuttals: int = Field(default=5, ge=0, le=10)
    realism: int = Field(default=5, ge=0, le=10)
    # Der Gesamtwert wird nach der Validierung immer neu berechnet; ein vom
    # Modell gelieferter Wert wird nie übernommen.
    total: int = Field(default=25, ge=0)

    @field_validator("total", mode="before")
    @classmethod
    def _total(cls, value: object) -> int:
        try:
            return int(float(str(value)))
        except (TypeError, ValueError):
            return 25

    def computed_total(self) -> int:
        return self.claims + self.logic + self.qualifiers + self.rebuttals + self.realism


class SurvivingArgument(BaseModel):
    claim: str
    why: str = ""


class RefutedArgument(BaseModel):
    side: Literal["pro", "contra"] = "pro"
    claim: str
    why: str = ""


class JudgeVerdict(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    winner: Literal["pro", "contra", "draw"] = "draw"
    summary: str = ""
    scores: dict[str, ScoreBlock] = Field(default_factory=dict)
    pro_surviving: list[SurvivingArgument] = Field(default_factory=list)
    contra_surviving: list[SurvivingArgument] = Field(default_factory=list)
    refuted: list[RefutedArgument] = Field(default_factory=list)
    open_conflicts: list[str] = Field(default_factory=list)
    architecture_rules: list[str] = Field(default_factory=list)

    @field_validator("pro_surviving", "contra_surviving", mode="before")
    @classmethod
    def _surviving(cls, value: object) -> list[object]:
        if value is None:
            return []
        if isinstance(value, str):
            return [{"claim": value, "why": ""}]
        return value if isinstance(value, list) else []

    @field_validator("refuted", mode="before")
    @classmethod
    def _refuted(cls, value: object) -> list[object]:
        if value is None:
            return []
        if isinstance(value, str):
            return [{"side": "pro", "claim": value, "why": ""}]
        return value if isinstance(value, list) else []

    @field_validator("open_conflicts", "architecture_rules", mode="before")
    @classmethod
    def _str_list(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        return []

    @field_validator("winner", mode="before")
    @classmethod
    def _winner(cls, value: object) -> str:
        raw = str(value or "").strip().lower()
        return raw if raw in {"pro", "contra", "draw"} else "draw"

    def pro_score(self) -> ScoreBlock:
        return self.scores.get("pro", ScoreBlock())

    def contra_score(self) -> ScoreBlock:
        return self.scores.get("contra", ScoreBlock())


class PlannerAction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    phase: str = "Informationsbeschaffung"
    target: str
    port: int = Field(default=443, ge=1, le=65535)
    action_type: Literal["READ_ONLY", "ACTIVE_REQUIRES_APPROVAL"] = "READ_ONLY"
    command: str
    risk: Literal["low", "medium", "high"] = "low"
    expected_evidence: str = ""


class PlannerOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    actions: list[PlannerAction] = Field(default_factory=list)
