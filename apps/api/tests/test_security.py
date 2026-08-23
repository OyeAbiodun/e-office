"""JWT infrastructure tests."""

from meetinghq_api.core.config import Settings
from meetinghq_api.core.security import JwtTokenCodec


def test_jwt_codec_round_trip() -> None:
    """The configured codec preserves subject and custom claims."""
    settings = Settings(jwt_secret="a-secure-test-secret-that-is-long-enough")  # noqa: S106
    codec = JwtTokenCodec(settings)

    token = codec.encode("user-123", {"role": "member"})
    claims = codec.decode(token)

    assert claims["sub"] == "user-123"
    assert claims["role"] == "member"
