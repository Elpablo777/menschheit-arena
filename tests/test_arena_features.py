"""Vertrag fuer Provider-Auswahl, freie Rundenzahl, Verlauf und LLM-Protokoll."""

from __future__ import annotations

from fastapi.testclient import TestClient

from menschheit.api.app import create_app
from menschheit.config import Settings
from menschheit.providers import OPENROUTER_FREE, catalogue
from menschheit.storage import Database

TOPIC = "Sollte die Menschheit die Kontrolle ueber KI an eine demokratische Institution abgeben?"


def make_client(**overrides) -> TestClient:
    settings = Settings(database_url="sqlite:///:memory:", provider="mock", **overrides)
    settings.default_rounds = 1
    return TestClient(create_app(settings=settings, database=Database("sqlite:///:memory:")))


def test_provider_catalogue_has_free_models() -> None:
    providers = {provider["id"]: provider for provider in catalogue()}
    assert "openrouter" in providers
    openrouter = providers["openrouter"]
    free = [model for model in openrouter["models"] if str(model["id"]).endswith(":free")]
    assert len(free) >= 5
    assert all(choice["id"] in {model["id"] for model in openrouter["models"]} for choice in OPENROUTER_FREE)
    assert providers["mock"]["needs_key"] is False
    assert providers["custom"]["needs_key"] is False
    assert providers["openai"]["needs_key"] is True
    assert {provider["id"] for provider in catalogue()} == {
        "openrouter",
        "deepseek",
        "openai",
        "mistral",
        "groq",
        "ollama",
        "litellm",
        "custom",
        "mock",
    }


def test_provider_test_reports_missing_base_url() -> None:
    client = make_client()
    result = client.post("/api/providers/test", json={"provider": "custom"}).json()
    assert result["ok"] is False
    assert "Base-URL" in result["message"]


def test_rounds_are_not_capped_at_eight() -> None:
    client = make_client()
    debate = client.post(
        "/api/arena/debates",
        json={"topic": TOPIC, "rounds": 40, "sync": True},
    ).json()
    assert debate["status"] == "completed"
    assert debate["rounds_requested"] == 40
    assert debate["rounds_actual"] == 40
    assert len(debate["turns"]) == 80


def test_transcript_lists_every_round() -> None:
    client = make_client()
    debate = client.post(
        "/api/arena/debates",
        json={"topic": TOPIC, "rounds": 6, "sync": True},
    ).json()
    transcript = client.get(f"/api/arena/debates/{debate['id']}/transcript").json()
    assert [block["round_no"] for block in transcript["rounds"]] == [1, 2, 3, 4, 5, 6]
    for block in transcript["rounds"]:
        assert block["pro"] and block["contra"]
        assert block["pro"]["public_argument"]
        assert block["contra"]["public_argument"]
        assert block["moderation"]
    assert transcript["debate"]["topic"] == TOPIC
    assert transcript["judgment"]["pass_ab"]["summary"]


def test_calls_expose_prompt_and_response() -> None:
    client = make_client()
    debate = client.post(
        "/api/arena/debates",
        json={"topic": TOPIC, "rounds": 2, "sync": True},
    ).json()
    calls = client.get(f"/api/arena/debates/{debate['id']}/calls").json()
    assert calls["count"] >= 8
    assert calls["total_tokens"] > 0
    first = calls["calls"][0]
    assert first["messages"]
    assert first["messages"][0]["role"] == "system"
    assert "Debatte" in first["messages"][0]["content"] or len(first["messages"][0]["content"]) > 100
    assert first["response_text"]
    assert first["parsed_ok"] is True
    assert first["round_no"] == 1
    assert first["model"]

    filtered = client.get(f"/api/arena/debates/{debate['id']}/calls?role=judge").json()
    assert filtered["count"] == 2
    assert all(call["role"] == "judge" for call in filtered["calls"])


def test_prompt_endpoint_returns_role_prompt() -> None:
    client = make_client()
    data = client.get("/api/prompts/pro/de").json()
    assert data["role"] == "pro"
    assert len(data["system_prompt"]) > 500
    assert client.get("/api/prompts/unknown/de").status_code == 404


def test_fork_creates_new_debate() -> None:
    client = make_client()
    source = client.post("/api/arena/debates", json={"topic": TOPIC, "rounds": 3, "sync": True}).json()
    forked = client.post(
        f"/api/arena/debates/{source['id']}/fork",
        json={"topic": "Ist KI-Forschung ohne offene Modelle verantwortbar?", "rounds": 2},
    )
    assert forked.status_code == 202
    body = forked.json()
    assert body["parent_debate_id"] == source["id"]
    assert body["rounds_requested"] == 2
    assert body["models"] == source["models"]


def test_delete_removes_debate_and_turns() -> None:
    client = make_client()
    debate = client.post("/api/arena/debates", json={"topic": TOPIC, "rounds": 1, "sync": True}).json()
    assert client.delete(f"/api/arena/debates/{debate['id']}").status_code == 200
    assert client.get(f"/api/arena/debates/{debate['id']}").status_code == 404
    assert client.get(f"/api/arena/debates/{debate['id']}/calls").status_code == 404


def test_settings_echo_config() -> None:
    client = make_client()
    debate = client.post(
        "/api/arena/debates",
        json={
            "topic": TOPIC,
            "rounds": 2,
            "sync": True,
            "config": {"word_limit": 180, "temperature": 0.4, "confidence_gate": 30},
        },
    ).json()
    assert debate["config"]["word_limit"] == 180
    assert debate["config"]["temperature"] == 0.4
    assert debate["config"]["confidence_gate"] == 30


def test_list_includes_round_counts() -> None:
    client = make_client()
    client.post("/api/arena/debates", json={"topic": TOPIC, "rounds": 3, "sync": True})
    listed = client.get("/api/arena/debates").json()
    assert listed
    assert listed[0]["rounds_actual"] == 3
    assert listed[0]["rounds_requested"] == 3