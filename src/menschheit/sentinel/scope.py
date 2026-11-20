"""Harte, deterministische Scope-Pruefung vor jedem Tool- oder MCP-Aufruf."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlparse

HOST_RE = re.compile(r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))*\.?$")
PRIVATE_SUFFIXES = (".local", ".internal", ".test", ".lab", ".localhost", ".home.arpa")
DEFAULT_PORTS = (80, 443)


class ScopeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Target:
    raw: str
    host: str
    port: int | None
    kind: str  # ip | domain | cidr | url
    scheme: str | None = None


@dataclass(frozen=True, slots=True)
class ScopeDecision:
    allowed: bool
    reason: str
    target: str
    host: str
    port: int
    kind: str


def _is_public_ip(value: ipaddress._BaseAddress) -> bool:
    return bool(value.is_global)


def _is_private_domain(host: str) -> bool:
    host = host.lower().rstrip(".")
    return host in {"localhost", "localhost.localdomain"} or host.endswith(PRIVATE_SUFFIXES)


def _validate_domain(host: str) -> str:
    host = host.lower().rstrip(".")
    if not host or "*" in host:
        raise ScopeError(f"Ungueltige Domain: {host!r}")
    if not HOST_RE.match(host):
        raise ScopeError(f"Ungueltige Domain: {host!r}")
    if host.replace(".", "").isdigit():
        raise ScopeError(f"Domain sieht wie eine IP aus: {host!r}")
    return host


def _validate_wildcard(entry: str) -> str:
    host = entry[2:].lower().rstrip(".")
    if not host or "*" in host:
        raise ScopeError(f"Ungueltiger Wildcard-Eintrag: {entry!r}")
    _validate_domain(host)
    if host.count(".") < 1:
        raise ScopeError(f"Wildcard braucht mindestens zwei Labels: {entry!r}")
    return f"*.{host}"


def parse_target(raw: str, default_port: int | None = None) -> Target:
    value = (raw or "").strip()
    if not value:
        raise ScopeError("Leeres Ziel.")
    if any(char in value for char in ("\n", "\r", "\x00")):
        raise ScopeError("Ziel enthaelt Steuerzeichen.")

    if "://" in value:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"}:
            raise ScopeError("Nur http/https-URLs sind erlaubt.")
        if parsed.username or parsed.password:
            raise ScopeError("URLs mit eingebetteten Zugangsdaten sind nicht erlaubt.")
        if not parsed.hostname:
            raise ScopeError("URL ohne Host.")
        try:
            port = parsed.port
        except ValueError as exc:
            raise ScopeError(f"Ungueltiger Port: {exc}") from None
        host = parsed.hostname.lower()
        return Target(raw=value, host=host, port=port or (443 if parsed.scheme == "https" else 80), kind="url", scheme=parsed.scheme)

    # Host:Port (aber nicht IPv6 ohne Klammern)
    if value.count(":") == 1 and not value.startswith("["):
        host_part, port_part = value.rsplit(":", 1)
        if port_part.isdigit():
            port = int(port_part)
            if not 1 <= port <= 65535:
                raise ScopeError("Port ausserhalb 1-65535.")
            return _parse_host_or_ip(host_part, port, value)
    return _parse_host_or_ip(value, default_port, value)


def _parse_host_or_ip(value: str, port: int | None, raw: str) -> Target:
    try:
        if "/" in value:
            network = ipaddress.ip_network(value, strict=False)
            return Target(raw=raw, host=str(network), port=port, kind="cidr")
        address = ipaddress.ip_address(value)
        return Target(raw=raw, host=str(address), port=port, kind="ip")
    except ValueError:
        pass
    host = _validate_domain(value)
    return Target(raw=raw, host=host, port=port, kind="domain")


class ScopeGuard:
    """Prueft Ziele gegen eine explizite Allowlist. Keine DNS-Aufloesung."""

    def __init__(
        self,
        scope_entries: list[str],
        allowed_ports: list[int] | None = None,
        *,
        allow_public_targets: bool = False,
    ) -> None:
        self.allow_public_targets = allow_public_targets
        self.ports = sorted({int(port) for port in (allowed_ports or DEFAULT_PORTS)})
        for port in self.ports:
            if not 1 <= port <= 65535:
                raise ScopeError(f"Ungueltiger Port: {port}")
        self.networks: list[tuple[ipaddress._BaseNetwork, str]] = []
        self.domains: list[tuple[str, str]] = []
        self.urls: list[tuple[str, int, str]] = []
        if not scope_entries:
            raise ScopeError("Der Scope darf nicht leer sein.")
        for entry in scope_entries:
            self._add_entry(entry)
        if not (self.networks or self.domains or self.urls):
            raise ScopeError("Der Scope enthaelt keinen gueltigen Eintrag.")

    def _add_entry(self, entry: str) -> None:
        raw = (entry or "").strip()
        if not raw:
            return
        if raw in {"*", "0.0.0.0/0", "::/0"}:
            raise ScopeError("Globale Wildcards sind verboten.")
        if raw.startswith("*."):
            host = _validate_wildcard(raw)
            self._assert_public_allowed(host, raw)
            self.domains.append((host, raw))
            return
        target = parse_target(raw)
        if target.kind == "url":
            if target.port not in self.ports:
                raise ScopeError(f"Port {target.port} ist nicht in den erlaubten Ports.")
            self._assert_public_allowed(target.host, raw)
            self.urls.append((target.host.lower(), int(target.port), raw))
            return
        if target.kind == "cidr":
            network = ipaddress.ip_network(target.host, strict=False)
            if network.prefixlen < 8:
                raise ScopeError(f"CIDR zu breit: {raw}. Mindestens /8 erforderlich.")
            if any(_is_public_ip(address) for address in (network.network_address, network.broadcast_address)):
                self._assert_public_allowed(str(network.network_address), raw)
            self.networks.append((network, raw))
            return
        if target.kind == "ip":
            address = ipaddress.ip_address(target.host)
            if _is_public_ip(address):
                self._assert_public_allowed(target.host, raw)
            self.networks.append((ipaddress.ip_network(f"{address}/{address.max_prefixlen}"), raw))
            return
        # Domain
        host = target.host.lower().rstrip(".")
        self._assert_public_allowed(host, raw)
        self.domains.append((host, raw))

    def _assert_public_allowed(self, host: str, raw: str) -> None:
        try:
            address = ipaddress.ip_address(host)
            public = _is_public_ip(address)
        except ValueError:
            public = not _is_private_domain(host)
        if public and not self.allow_public_targets:
            raise ScopeError(
                f"Oeffentliches Ziel {raw!r} ist blockiert. "
                "Setze ALLOW_PUBLIC_TARGETS=true erst nach schriftlicher RoE und Rechtspruefung."
            )

    def check(self, target: str, port: int | None = None) -> ScopeDecision:
        try:
            parsed = parse_target(target, port)
        except ScopeError as exc:
            return ScopeDecision(False, str(exc), target, "", 0, "invalid")
        effective_port = parsed.port or (self.ports[0] if self.ports else 443)
        if effective_port not in self.ports:
            return ScopeDecision(
                False,
                f"Port {effective_port} ist nicht freigegeben (erlaubt: {self.ports}).",
                target,
                parsed.host,
                effective_port,
                parsed.kind,
            )
        if parsed.kind == "cidr":
            # Ein CIDR ist selbst kein einzelnes Angriffsziel. Der Executor muss
            # konkrete Hosts erneut gegen die Allowlist pruefen.
            return ScopeDecision(False, "CIDR ist kein einzelnes Ziel; konkreten Host angeben.", target, parsed.host, effective_port, parsed.kind)

        host = parsed.host.lower().rstrip(".")
        matched = ""
        if parsed.kind == "ip":
            address = ipaddress.ip_address(host)
            for network, raw in self.networks:
                if address.version == network.version and address in network:
                    matched = raw
                    break
            if not matched:
                return ScopeDecision(False, "IP liegt nicht in einem freigegebenen Netz.", target, host, effective_port, parsed.kind)
        elif parsed.kind in {"domain", "url"}:
            for domain, raw in self.domains:
                if domain.startswith("*."):
                    suffix = domain[1:]
                    if host.endswith(suffix) and host != suffix[1:]:
                        matched = raw
                        break
                elif host == domain:
                    matched = raw
                    break
            if not matched:
                for url_host, url_port, raw in self.urls:
                    if host == url_host and effective_port == url_port:
                        matched = raw
                        break
            if not matched:
                return ScopeDecision(
                    False,
                    "Host ist nicht in der Domain-Allowlist. CIDR-Eintraege autorisieren keine Hostnamen (DNS-Rebinding-Schutz).",
                    target,
                    host,
                    effective_port,
                    parsed.kind,
                )
        elif parsed.kind == "url":
            matched = target

        try:
            address = ipaddress.ip_address(host)
            public = _is_public_ip(address)
        except ValueError:
            public = not _is_private_domain(host)
        if public and not self.allow_public_targets:
            return ScopeDecision(False, "Oeffentliche Ziele sind deaktiviert.", target, host, effective_port, parsed.kind)
        return ScopeDecision(True, f"Erlaubt durch Scope-Eintrag {matched!r}.", target, host, effective_port, parsed.kind)

    def allows_network(self, cidr: str) -> ScopeDecision:
        """Erlaubt eine Netz-Discovery nur bei exakt freigegebenem CIDR."""
        try:
            requested = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            return ScopeDecision(False, "Ungueltiges CIDR.", cidr, "", 0, "cidr")
        for network, raw in self.networks:
            if requested.version == network.version and requested.subnet_of(network):
                try:
                    address = requested.network_address
                    public = _is_public_ip(address)
                except ValueError:
                    public = False
                if public and not self.allow_public_targets:
                    return ScopeDecision(False, "Oeffentliche Netze sind deaktiviert.", cidr, str(requested), 0, "cidr")
                return ScopeDecision(True, f"Erlaubt durch Netz-Eintrag {raw!r}; Hosts muessen vor Ausfuehrung erneut geprueft werden.", cidr, str(requested), 0, "cidr")
        return ScopeDecision(False, "CIDR ist nicht freigegeben.", cidr, str(requested), 0, "cidr")

    def public_dict(self) -> dict[str, object]:
        return {
            "ports": self.ports,
            "allow_public_targets": self.allow_public_targets,
            "entries": [raw for _, raw in self.networks] + [raw for _, raw in self.domains] + [raw for _, _, raw in self.urls],
        }


def normalize_scope(entries: list[str], allowed_ports: list[int], allow_public_targets: bool = False) -> list[str]:
    cleaned = [entry.strip() for entry in entries if entry and entry.strip()]
    ScopeGuard(cleaned, allowed_ports, allow_public_targets=allow_public_targets)
    return cleaned
