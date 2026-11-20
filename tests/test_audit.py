from __future__ import annotations

import hashlib

import pytest
from sqlalchemy.exc import IntegrityError

from menschheit.storage import Database, Repository

ROE = (
    "Schriftliche Freigabe fuer lokale Tests. Keine externen Ziele, "
    "Notfallkontakt dokumentiert, Kill-Switch vereinbart."
)


def make_repo() -> tuple[Database, Repository]:
    db = Database("sqlite:///:memory:")
    return db, Repository(db)


def create_engagement(repo: Repository) -> dict:
    return repo.create_engagement(
        client_name="Audit-Kunde",
        roe_text=ROE,
        roe_hash=hashlib.sha256(ROE.encode("utf-8")).hexdigest(),
        scope=["127.0.0.1"],
        ports=[80, 443],
        valid_from="2026-01-01",
        valid_until="2099-12-31",
        authorized_by="Max Mustermann",
        emergency_contact="security@example.test",
    )


def test_audit_chain_is_valid_and_linked() -> None:
    _, repo = make_repo()
    engagement = create_engagement(repo)
    repo.audit(engagement["id"], "tester", "second.event", {"b": 2})
    repo.audit(engagement["id"], "tester", "third.event", {"c": 3})
    repo.audit(engagement["id"], "tester", "fourth.event", {"d": 4})

    valid, errors = repo.verify_audit_chain()
    assert valid is True
    assert errors == []
    events = repo.list_audit(engagement["id"])
    assert events[0]["prev_hash"] == ""
    assert events[1]["prev_hash"] == events[0]["hash"]
    assert events[2]["prev_hash"] == events[1]["hash"]


def test_audit_is_append_only() -> None:
    db, repo = make_repo()
    engagement = create_engagement(repo)
    repo.audit(engagement["id"], "tester", "test.event", {"a": 1})
    with pytest.raises(IntegrityError):
        db.execute("UPDATE audit_events SET actor = 'manipuliert'")
    with pytest.raises(IntegrityError):
        db.execute("DELETE FROM audit_events")
    valid, _ = repo.verify_audit_chain()
    assert valid is True


def test_engagement_roe_hash_is_stable() -> None:
    _, repo = make_repo()
    engagement = create_engagement(repo)
    assert len(engagement["roe_hash"]) == 64
    assert create_engagement(repo)["roe_hash"] == engagement["roe_hash"]
