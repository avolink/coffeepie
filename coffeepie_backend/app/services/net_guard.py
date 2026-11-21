"""Outbound-target guard for server-side requests (SSRF defence).

A caller-supplied address may only be contacted if it is a literal IP that sits
inside an operator-approved network. Fails closed: with no approved networks
configured, nothing is allowed.

    SUNSHINE_ALLOWED_NETWORKS=10.20.0.0/16,192.168.50.0/24
"""
import ipaddress
import os


class TargetNotAllowed(ValueError):
    pass


def _allowed_networks():
    raw = os.getenv("SUNSHINE_ALLOWED_NETWORKS", "")
    nets = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            nets.append(ipaddress.ip_network(part, strict=False))
    return nets


def require_allowed_target(host: str) -> str:
    """Return the normalised IP if it may be contacted, else raise TargetNotAllowed."""
    try:
        ip = ipaddress.ip_address(str(host).strip())
    except ValueError:
        # Hostnames are refused on purpose: they can resolve to anything.
        raise TargetNotAllowed("Target must be a literal IP address")

    if (ip.is_loopback or ip.is_link_local or ip.is_multicast
            or ip.is_unspecified or ip.is_reserved):
        raise TargetNotAllowed("Target address is not permitted")

    nets = _allowed_networks()
    if not nets:
        raise TargetNotAllowed("No SUNSHINE_ALLOWED_NETWORKS configured")
    if not any(ip in net for net in nets if net.version == ip.version):
        raise TargetNotAllowed("Target address is outside the allowed networks")
    return str(ip)
