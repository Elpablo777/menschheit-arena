"""API-Eingabeschemata mit strikter Validierung."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..i18n import normalize_lang


class DebateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=8, max_length=2000)
    rounds: int | None = Field(default=None, ge=1, le=8)
    language: str = "de"
    models: dict[str, str] | None = None
    sync: bool = False

    @field_validator("language", mode="before")
    @classmethod
    def _lang(cls, value: object) -> str:
        return normalize_lang(str(value or "de"))

    @field_validator("topic")
    @classmethod
    def _topic(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 8:
            raise ValueError("Thema ist zu kurz.")
        return cleaned

    @field_validator("models")
    @classmethod
    def _models(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return None
        allowed = {"pro", "contra", "judge", "moderator"}
        cleaned: dict[str, str] = {}
        for role, model in value.items():
            if role not in allowed:
                raise ValueError(f"Unbekannte Rolle: {role}")
            model = str(model).strip()
            if not model or len(model) > 120:
                raise ValueError(f"Ungueltiger Modellname fuer {role}")
            cleaned[role] = model
        return cleaned


class EngagementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_name: str = Field(min_length=2, max_length=200)
    scope: list[str] = Field(min_length=1, max_length=50)
    ports: list[int] = Field(min_length=1, max_length=20)
    valid_from: str
    valid_until: str
    roe_text: str = Field(min_length=50, max_length=20000)
    authorized_by: str = Field(min_length=2, max_length=200)
    emergency_contact: str = Field(min_length=2, max_length=500)

    @field_validator("scope")
    @classmethod
    def _scope(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError("Scope darf nicht leer sein.")
        return cleaned

    @field_validator("ports")
    @classmethod
    def _ports(cls, value: list[int]) -> list[int]:
        ports = sorted({int(port) for port in value})
        if any(port < 1 or port > 65535 for port in ports):
            raise ValueError("Ports muessen zwischen 1 und 65535 liegen.")
        return ports


class ApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approver: str = Field(min_length=2, max_length=200)


class RejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor: str = Field(default="human", max_length=200)
    reason: str = Field(default="", max_length=1000)


class KillSwitchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor: str = Field(default="human", max_length=200)


class FindingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=300)
    owasp_ref: str = Field(default="", max_length=120)
    cvss_vector: str = Field(default="", max_length=300)
    evidence: str = Field(min_length=10, max_length=20000)
    remediation: str = Field(min_length=10, max_length=20000)
    verified_by_human: bool = False
    actor: str = Field(default="human", max_length=200)


class ValidateTargetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str = Field(min_length=1, max_length=2000)
    port: int | None = Field(default=None, ge=1, le=65535)
    scope: list[str] = Field(min_length=1, max_length=50)
    ports: list[int] = Field(default_factory=lambda: [80, 443], max_length=20)


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["rules", "llm"] = "rules"
    language: str = "de"

    @field_validator("language", mode="before")
    @classmethod
    def _lang(cls, value: object) -> str:
        return normalize_lang(str(value or "de"))
