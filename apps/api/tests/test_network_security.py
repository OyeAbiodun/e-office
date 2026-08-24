"""Security tests for administrator-controlled outbound endpoints."""

import socket

import pytest

from meetinghq_api.core.network import UnsafeEndpointError, validate_public_http_endpoint


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://127.0.0.1/admin",
        "http://[::1]/admin",
        "http://169.254.169.254/latest/meta-data",
        "http://localhost:8000/api",
        "http://user:password@example.com/api",
        "file:///etc/passwd",
    ],
)
async def test_private_or_credentialed_provider_endpoints_are_rejected(endpoint: str) -> None:
    with pytest.raises(UnsafeEndpointError):
        await validate_public_http_endpoint(endpoint)


async def test_dns_names_resolving_to_private_addresses_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.4", 443))],
    )

    with pytest.raises(UnsafeEndpointError):
        await validate_public_http_endpoint("https://provider.example/api")


async def test_public_provider_endpoint_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )

    assert (
        await validate_public_http_endpoint("https://provider.example/api")
        == "https://provider.example/api"
    )
