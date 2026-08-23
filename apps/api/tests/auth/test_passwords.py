"""Password policy and hashing tests."""

import pytest

from meetinghq_api.modules.auth.infrastructure.passwords import (
    PasswordPolicyError,
    hash_password,
    verify_password,
)


def test_argon2_password_round_trip() -> None:
    """Argon2 hashes verify the original password and reject others."""
    encoded = hash_password("Secure!Password123")
    assert encoded.startswith("$argon2id$")
    assert verify_password(encoded, "Secure!Password123")
    assert not verify_password(encoded, "Wrong!Password123")


@pytest.mark.parametrize(
    "password",
    ["short", "alllowercase123!", "ALLUPPERCASE123!", "NoNumbersHere!", "NoSymbolsHere123"],
)
def test_password_policy_rejects_weak_passwords(password: str) -> None:
    """Every password complexity dimension is enforced."""
    with pytest.raises(PasswordPolicyError):
        hash_password(password)
