"""Network-boundary validation for administrator-configured provider endpoints."""

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeEndpointError(ValueError):
    """Raised when an outbound endpoint could reach a non-public network."""


async def validate_public_http_endpoint(endpoint: str) -> str:
    """Allow only public HTTP(S) endpoints and reject private DNS resolutions.

    Provider endpoints are administrator supplied, so treating a syntactically valid URL
    as trusted would expose instance metadata and internal services to SSRF.
    """
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise UnsafeEndpointError("Provider endpoint must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise UnsafeEndpointError("Provider endpoint must not contain embedded credentials")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
        raise UnsafeEndpointError("Provider endpoint must resolve to a public network")
    try:
        addresses = await asyncio.to_thread(_resolve_addresses, hostname, parsed.port)
    except (OSError, socket.gaierror) as exc:
        raise UnsafeEndpointError("Provider endpoint DNS resolution failed") from exc
    if not addresses or any(not _is_public(address) for address in addresses):
        raise UnsafeEndpointError("Provider endpoint must resolve only to public networks")
    return endpoint


def _resolve_addresses(hostname: str, port: int | None) -> set[str]:
    return {
        str(item[4][0])
        for item in socket.getaddrinfo(hostname, port or 443, type=socket.SOCK_STREAM)
    }


def _is_public(address: str) -> bool:
    value = ipaddress.ip_address(address)
    return not any(
        (
            value.is_private,
            value.is_loopback,
            value.is_link_local,
            value.is_multicast,
            value.is_reserved,
            value.is_unspecified,
        )
    )
