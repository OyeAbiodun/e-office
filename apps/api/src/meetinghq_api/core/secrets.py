"""Authenticated encryption for provider credentials stored in the database."""

import base64
import hashlib
import json
from typing import cast

from cryptography.fernet import Fernet, InvalidToken

from meetinghq_api.shared.exceptions import ConflictError


class SecretVault:
    """Seal JSON values using an installation-specific authenticated key."""

    VERSION = 1

    def __init__(self, installation_secret: str) -> None:
        key = base64.urlsafe_b64encode(hashlib.sha256(installation_secret.encode()).digest())
        self._fernet = Fernet(key)

    def seal(self, value: dict[str, object]) -> dict[str, object]:
        payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
        return {
            "sealed": self._fernet.encrypt(payload).decode(),
            "version": self.VERSION,
        }

    def open(self, value: dict[str, object]) -> dict[str, object]:
        token = value.get("sealed")
        if not isinstance(token, str):
            return value
        try:
            decoded = json.loads(self._fernet.decrypt(token.encode()))
        except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ConflictError(
                "Provider credentials cannot be decrypted with this installation key"
            ) from error
        if not isinstance(decoded, dict):
            raise ConflictError("Provider credentials have an invalid encrypted payload")
        return cast(dict[str, object], decoded)

    @staticmethod
    def is_sealed(value: dict[str, object]) -> bool:
        return isinstance(value.get("sealed"), str)
