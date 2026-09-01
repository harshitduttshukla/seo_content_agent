"""SSRF and URL safety validation."""

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.errors import DomainError


class SSRFSecurityError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__("SSRF_BLOCKED", message, http_status=400)


_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
    # IPv6
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
]


def is_ip_blocked(ip_addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address falls within any blocked/private/link-local ranges."""
    return any(ip_addr in network for network in _BLOCKED_NETWORKS)


def validate_safe_url(url: str, *, resolve_dns: bool = True) -> str:
    """Validate that a URL uses http/https and does not point to internal/private infrastructure."""
    if not url or not isinstance(url, str):
        raise SSRFSecurityError("URL is empty or invalid.")

    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise SSRFSecurityError(
            f"Disallowed URL scheme '{scheme}'. Only http and https are permitted."
        )

    hostname = parsed.hostname
    if not hostname:
        raise SSRFSecurityError("URL must contain a valid hostname.")

    hostname = hostname.lower().strip()

    # Block well-known localhost / cloud metadata aliases immediately
    blocked_hosts = {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "instance-data",
    }
    if hostname in blocked_hosts or hostname.endswith(".localhost"):
        raise SSRFSecurityError(f"Access to blocked hostname '{hostname}' is prohibited.")

    # Check if host is direct IP
    try:
        ip_obj = ipaddress.ip_address(hostname)
        if is_ip_blocked(ip_obj):
            raise SSRFSecurityError(
                f"Access to private/reserved IP address '{ip_obj}' is prohibited."
            )
        return url
    except ValueError:
        # Not a direct IP, hostname is a domain name
        pass

    if resolve_dns:
        try:
            # Resolve both IPv4 and IPv6 addresses
            addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            if not addr_info:
                raise SSRFSecurityError(f"Could not resolve host '{hostname}'.")
            for _family, _, _, _, sockaddr in addr_info:
                ip_str = sockaddr[0]
                ip_obj = ipaddress.ip_address(ip_str)
                if is_ip_blocked(ip_obj):
                    raise SSRFSecurityError(
                        f"Resolved hostname '{hostname}' points to private/reserved IP '{ip_str}'."
                    )
        except socket.gaierror as exc:
            raise SSRFSecurityError(
                f"DNS resolution failed for hostname '{hostname}': {exc}"
            ) from exc

    return url
