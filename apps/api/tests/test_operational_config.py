"""Fail-closed staging and production configuration coverage."""

import pytest
from pydantic import ValidationError

from meetinghq_api.core.config import Settings


def test_production_rejects_development_defaults() -> None:
    with pytest.raises(ValidationError, match="Unsafe deployment configuration"):
        Settings(environment="production")


def test_production_rejects_process_local_storage() -> None:
    with pytest.raises(ValidationError, match="production object storage"):
        Settings(
            environment="production",
            jwt_secret="release-candidate-secret-value-with-32-chars",  # noqa: S106
            secure_cookies=True,
            redis_url="redis://cache.internal:6379/0",
            auth_rate_limit_fail_closed=True,
            web_app_url="https://app.meetinghq.example",
            api_cors_origins=["https://app.meetinghq.example"],
            trusted_hosts=["api.meetinghq.example"],
            storage_provider="local",
        )


def test_staging_accepts_explicit_secure_configuration() -> None:
    settings = Settings(
        environment="staging",
        jwt_secret="release-candidate-secret-value-with-32-chars",  # noqa: S106
        secure_cookies=True,
        redis_url="redis://cache.internal:6379/0",
        auth_rate_limit_fail_closed=True,
        web_app_url="https://staging.meetinghq.example",
        api_cors_origins=["https://staging.meetinghq.example"],
        trusted_hosts=["api.staging.meetinghq.example"],
        storage_provider="local",
    )

    assert settings.environment == "staging"
