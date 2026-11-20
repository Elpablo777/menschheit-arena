from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from menschheit.api.app import create_app
from menschheit.config import Settings
from menschheit.storage import Database

ROE = (
    "Signierte Freigabe fuer lokale Tests. Keine externen Ziele, keine Datenexfiltration, "
    "Notfallkontakt dokumentiert und Kill-Switch vereinbart."
)


def make_client(**overrides) -> TestClient:
    settings = Settings(database_url="sqlite:///:memory:", provider="mock", **overrides)
    settings.default_rounds = 2
    app = create_app(settings=settings, database=Database("sqlite:///:memory:"))
    return TestClient(app)


@pytest.fixture()
def client():
    with make_client() as test_client:
        yield test_client


def engagement_payload() -> dict:
    today = date.today()
    return {
        "client_name": "Testkunde GmbH",
        "scope": ["127.0.0.1", "app.lab.test"],
        "ports": [80, 443],
        "valid_from": today.isoformat(),
        "valid_until": (today + timedelta(days=30)).isoformat(),
        "roe_text": ROE,
        "authorized_by": "Max Mustermann",
        "emergency_contact": "security@example.test",
    }


def test_health_config_and_i18n(client: TestClient) -> None:
    health = client.get("/api/health").json()
    assert health["status"] == "ok"
    assert health["database"] is True
    assert health["mock"] is True

    config = client.get("/api/config").json()
    assert config["mock"] is True
    assert config["pentest_execution_enabled"] is False
    assert config["allow_public_targets"] is False
    assert "llm_api_key" not in config

    messages = client.get("/api/i18n/en").json()
    assert messages["lang"] == "en"
    assert messages["messages"]["app.name"] == "Menschheit Arena"


def test_index_is_served(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Menschheit Arena" in response.text
    assert "/static/app.js" in response.text


def test_debate_sync_end_to_end(client: TestClient) -> None:
    response = client.post(
        "/api/arena/debates",
        json={"topic": "Sollte die Menschheit die Kontrolle ueber KI abgeben?", "rounds": 2, "sync": True},
    )
    assert response.status_code == 202
    debate = response.json()
    assert debate["status"] == "completed"
    assert len(debate["turns"]) == 4
    assert debate["judgment"] is not None

    report = client.get(f"/api/arena/debates/{debate['id']}/report.md")
    assert report.status_code == 200
    assert "Debattenbericht" in report.text

    listing = client.get("/api/arena/debates").json()
    assert any(item["id"] == debate["id"] for item in listing)


def test_debate_validation(client: TestClient) -> None:
    assert client.post("/api/arena/debates", json={"topic": "kurz"}).status_code == 422
    # 2000 Runden sind erlaubt, 2001 nicht.
    assert (
        client.post(
            "/api/arena/debates",
            json={"topic": "Ein ausreichend langes Thema", "rounds": 2001},
        ).status_code
        == 422
    )


def test_sentinel_flow(client: TestClient) -> None:
    response = client.post("/api/sentinel/engagements", json=engagement_payload())
    assert response.status_code == 201
    engagement = response.json()
    assert "roe_text" not in engagement
    engagement_id = engagement["id"]

    response = client.post(
        f"/api/sentinel/engagements/{engagement_id}/plan", json={"mode": "rules", "language": "de"}
    )
    assert response.status_code == 200
    actions = response.json()["actions"]
    assert actions
    assert all(action["scope_allowed"] for action in actions)

    active = next(action for action in actions if action["approval_required"])
    denied = client.post(f"/api/sentinel/actions/{active['id']}/approve", json={"approver": "M"})
    assert denied.status_code == 422
    approved = client.post(
        f"/api/sentinel/actions/{active['id']}/approve", json={"approver": "Max Mustermann"}
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    finding = client.post(
        f"/api/sentinel/engagements/{engagement_id}/findings",
        json={
            "title": "Fehlender Security-Header",
            "owasp_ref": "A05:2021",
            "cvss_vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:L/VI:L/VA:L/SC:N/SI:N/SA:N",
            "evidence": "Response ohne Content-Security-Policy, reproduzierbar per curl.",
            "remediation": "CSP-Header mit restriktiver Policy ergaenzen.",
            "verified_by_human": True,
            "actor": "Max Mustermann",
        },
    )
    assert finding.status_code == 201

    detail = client.get(f"/api/sentinel/engagements/{engagement_id}").json()
    assert detail["audit_valid"] is True
    assert len(detail["audit"]) >= 5
    assert len(detail["findings"]) == 1

    report = client.get(f"/api/sentinel/engagements/{engagement_id}/report.md?lang=de")
    assert report.status_code == 200
    assert "Fehlender Security-Header" in report.text

    killed = client.post(
        f"/api/sentinel/engagements/{engagement_id}/kill", json={"actor": "Max Mustermann"}
    )
    assert killed.status_code == 200
    assert killed.json()["kill_switch"] is True
    blocked_plan = client.post(
        f"/api/sentinel/engagements/{engagement_id}/plan", json={"mode": "rules"}
    )
    assert blocked_plan.status_code == 400


def test_public_targets_are_denied(client: TestClient) -> None:
    response = client.post(
        "/api/sentinel/validate",
        json={"target": "https://example.com", "scope": ["https://example.com"], "ports": [80, 443]},
    )
    assert response.status_code == 400
    assert "blockiert" in response.json()["detail"]

    allowed = client.post(
        "/api/sentinel/validate",
        json={"target": "https://app.lab.test", "scope": ["app.lab.test"], "ports": [443]},
    )
    assert allowed.status_code == 200
    assert allowed.json()["allowed"] is True


def test_access_token_protects_mutations() -> None:
    with make_client(access_token="streng-geheim") as client:
        assert client.get("/api/health").status_code == 200
        payload = {"target": "app.lab.test", "scope": ["app.lab.test"], "ports": [443]}
        assert client.post("/api/sentinel/validate", json=payload).status_code == 401
        assert (
            client.post(
                "/api/sentinel/validate", json=payload, headers={"X-App-Token": "streng-geheim"}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/sentinel/validate",
                json=payload,
                headers={"Authorization": "Bearer streng-geheim"},
            ).status_code
            == 200
        )
