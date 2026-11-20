from __future__ import annotations

import pytest

from menschheit.sentinel.scope import ScopeError, ScopeGuard, parse_target


def guard(entries: list[str], ports: list[int] | None = None, public: bool = False) -> ScopeGuard:
    return ScopeGuard(entries, ports or [80, 443], allow_public_targets=public)


def test_private_ip_and_network_allowed() -> None:
    scope = guard(["127.0.0.1", "10.0.0.0/24"])
    assert scope.check("127.0.0.1", 443).allowed
    assert scope.check("10.0.0.5", 443).allowed
    assert not scope.check("10.1.0.5", 443).allowed


def test_domain_and_wildcard() -> None:
    scope = guard(["app.lab.test", "*.lab.test"])
    assert scope.check("https://app.lab.test").allowed
    assert scope.check("api.lab.test", 443).allowed
    assert not scope.check("lab.test", 443).allowed
    assert not scope.check("lab.test.evil.example.com", 443).allowed


def test_public_targets_blocked_by_default() -> None:
    with pytest.raises(ScopeError):
        guard(["example.com"])
    with pytest.raises(ScopeError):
        guard(["1.1.1.1"])
    allowed = guard(["example.com"], public=True)
    assert allowed.check("example.com", 443).allowed


def test_global_wildcards_rejected() -> None:
    for entry in ("*", "0.0.0.0/0", "::/0"):
        with pytest.raises(ScopeError):
            guard([entry])


def test_port_allowlist_enforced() -> None:
    scope = guard(["app.lab.test"], ports=[443])
    assert scope.check("app.lab.test", 443).allowed
    decision = scope.check("app.lab.test", 80)
    assert not decision.allowed
    assert "Port 80" in decision.reason


def test_cidr_is_not_a_single_target() -> None:
    scope = guard(["10.0.0.0/24"])
    assert not scope.check("10.0.0.0/24").allowed
    assert scope.allows_network("10.0.0.0/24").allowed
    assert not scope.allows_network("10.0.1.0/24").allowed


def test_cidr_does_not_authorise_hostnames() -> None:
    scope = guard(["10.0.0.0/24"])
    assert not scope.check("app.lab.test", 443).allowed


def test_url_with_credentials_rejected() -> None:
    with pytest.raises(ScopeError):
        parse_target("https://user:pass@app.lab.test")
    with pytest.raises(ScopeError):
        parse_target("ftp://app.lab.test")


def test_url_entry_matches_exact_port() -> None:
    scope = guard(["https://app.lab.test"], ports=[80, 443])
    assert scope.check("https://app.lab.test", 443).allowed
    assert scope.check("app.lab.test", 443).allowed
    assert not scope.check("app.lab.test", 80).allowed


def test_empty_or_invalid_scope_rejected() -> None:
    with pytest.raises(ScopeError):
        guard([])
    with pytest.raises(ScopeError):
        guard(["not a target"])
