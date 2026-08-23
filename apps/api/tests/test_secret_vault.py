"""Provider credential encryption guarantees."""

from meetinghq_api.core.secrets import SecretVault


def test_secret_vault_seals_and_authenticates_provider_values() -> None:
    vault = SecretVault("installation-secret-with-at-least-thirty-two-characters")
    original: dict[str, object] = {
        "host": "smtp.example.com",
        "password": "provider-secret",
    }
    sealed = vault.seal(original)
    assert SecretVault.is_sealed(sealed)
    assert "provider-secret" not in str(sealed)
    assert vault.open(sealed) == original
