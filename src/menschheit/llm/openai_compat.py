"""OpenAI-kompatibler Client fuer OpenRouter, DeepSeek, Mistral, Ollama, LiteLLM."""

from __future__ import annotations

import time
from typing import Any

import httpx

from .base import LLMError, LLMResult


class OpenAICompatClient:
    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        *,
        timeout: float = 90.0,
        provider: str = "openai_compat",
        default_temperature: float = 0.7,
        default_max_tokens: int = 1400,
    ) -> None:
        if not base_url or not base_url.startswith(("http://", "https://")):
            raise LLMError("LLM_BASE_URL fehlt oder ist keine gueltige http(s)-URL.")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.provider = provider
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens

    @property
    def endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://localhost/menschheit-arena"
            headers["X-Title"] = "Menschheit Arena"
        return headers

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        purpose: str = "generic",
        meta: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
        if not model:
            raise LLMError(f"Kein Modell fuer Rolle '{purpose}' konfiguriert.")
        payload = {
            "model": model,
            "messages": messages,
            "temperature": self.default_temperature if temperature is None else temperature,
            "max_tokens": self.default_max_tokens if max_tokens is None else max_tokens,
            "stream": False,
        }
        started = time.perf_counter()
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                    response = client.post(self.endpoint, headers=self._headers(), json=payload)
                if response.status_code in {408, 409, 425, 429, 500, 502, 503, 504} and attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                if response.status_code >= 400:
                    body = response.text[:500].replace("\n", " ")
                    raise LLMError(f"Provider HTTP {response.status_code}: {body}")
                data = response.json()
                choices = data.get("choices") or []
                if not choices:
                    raise LLMError("Provider lieferte keine choices zurueck.")
                message = choices[0].get("message") or {}
                content = message.get("content")
                if isinstance(content, list):
                    content = "".join(
                        part.get("text", "") for part in content if isinstance(part, dict)
                    )
                if not isinstance(content, str) or not content.strip():
                    raise LLMError("Provider lieferte leeren Inhalt.")
                usage = data.get("usage") or {}
                return LLMResult(
                    text=content.strip(),
                    model=str(data.get("model") or model),
                    prompt_tokens=int(usage.get("prompt_tokens") or 0),
                    completion_tokens=int(usage.get("completion_tokens") or 0),
                    raw=response.text[:20000],
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    meta={"provider": self.provider, "purpose": purpose},
                )
            except LLMError as exc:
                last_error = exc
                text = str(exc)
                if any(marker in text for marker in ("HTTP 400", "HTTP 401", "HTTP 403", "HTTP 404", "HTTP 422")):
                    break
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1.0)
        if isinstance(last_error, LLMError):
            raise last_error
        raise LLMError(f"LLM-Aufruf fehlgeschlagen: {type(last_error).__name__}: {str(last_error)[:200]}")
