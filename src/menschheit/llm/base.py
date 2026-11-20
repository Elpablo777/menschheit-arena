"""Provider-agnostische LLM-Schnittstelle."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class LLMError(RuntimeError):
    """Fehler eines LLM-Providers, ohne Secrets in der Meldung."""


@dataclass(slots=True)
class LLMResult:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: str = ""
    parsed: Any = None
    parsed_ok: bool = False
    error: str | None = None
    duration_ms: int = 0
    meta: dict[str, Any] = field(default_factory=dict)

    # Kompatible Namen
    @property
    def input_tokens(self) -> int:
        return self.prompt_tokens

    @property
    def output_tokens(self) -> int:
        return self.completion_tokens

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLMClient(Protocol):
    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        purpose: str = "generic",
        meta: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult: ...