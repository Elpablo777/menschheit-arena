"""Vertrag zwischen UI und API: Feldnamen, Booleans, i18n-Schluessel."""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from menschheit.api.app import create_app
from menschheit.config import Settings
from menschheit.storage import Database

WEB = Path(__file__).resolve().parents[1] / "src" / "menschheit" / "web"


@pytest.fixture(scope="module")
def api() -> TestClient:
    settings = Settings(database_url="sqlite:///:memory:", provider="mock")
    settings.default_rounds = 1
    app = create_app(settings=settings, database=Database("sqlite:///:memory:"))
    return TestClient(app)


def test_html_is_self_contained_and_translated(api: TestClient) -> None:
    html = api.get("/").text
    assert "Menschheit Arena" in html
    assert html.count("data-i18n") > 50
    assert '"""' not in html, "Python-Docstring im Template"
    assert "cdn." not in html
    # Erlaubt sind nur Beispielziele in Platzhaltern, keine geladenen Ressourcen.
    externals = {
        url
        for url in re.findall(r'(?:src|href)="(https?://[^"]+)"', html)
    }
    assert externals == set(), externals

    de = api.get("/api/i18n/de").json()["messages"]
    keys = set(re.findall(r'data-i18n(?:-placeholder|-aria-label)?="([a-zA-Z0-9_.]+)"', html))
    assert keys
    assert keys <= set(de)


def test_css_covers_all_dynamic_classes(api: TestClient) -> None:
    css = api.get("/static/styles.css").text
    js = api.get("/static/app.js").text
    defined = set(re.findall(r"\.([a-zA-Z][a-zA-Z0-9_-]*)", css))
    used = {
        token
        for group in re.findall(r'class="([a-z0-9 -]+)"', js)
        for token in group.split(" ")
    }
    assert used
    assert used <= defined


def test_backend_returns_true_booleans(api: TestClient) -> None:
    debate = api.post(
        "/api/arena/debates",
        json={"topic": "Sollte die Menschheit die Kontrolle ueber KI abgeben?", "rounds": 1, "sync": True},
    ).json()
    assert debate["status"] == "completed"
    assert debate["moderations"]
    for moderation in debate["moderations"]:
        assert isinstance(moderation["sycophancy"], bool)
        assert isinstance(moderation["drift"], bool)

    today = date.today()
    engagement = api.post(
        "/api/sentinel/engagements",
        json={
            "client_name": "UI-Vertrag",
            "scope": ["127.0.0.1"],
            "ports": [443],
            "valid_from": today.isoformat(),
            "valid_until": (today + timedelta(days=30)).isoformat(),
            "roe_text": "Signierte Freigabe fuer lokale Tests ohne externe Ziele und ohne Datenexfiltration.",
            "authorized_by": "Max Mustermann",
            "emergency_contact": "security@example.test",
        },
    ).json()
    assert "roe_text" not in engagement

    plan = api.post(
        f"/api/sentinel/engagements/{engagement['id']}/plan", json={"mode": "rules"}
    ).json()
    for action in plan["actions"]:
        assert isinstance(action["scope_allowed"], bool)
        assert isinstance(action["approval_required"], bool)


def test_validate_response_shape(api: TestClient) -> None:
    decision = api.post(
        "/api/sentinel/validate",
        json={"target": "127.0.0.1", "scope": ["127.0.0.1"], "ports": [443]},
    ).json()
    assert decision["allowed"] is True
    for field in ("reason", "target", "host", "port", "kind"):
        assert field in decision


def test_static_files_exist_in_package() -> None:
    for relative in ("templates/index.html", "static/app.js", "static/styles.css"):
        assert (WEB / relative).exists()