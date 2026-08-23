"""Argon2 password hashing and password policy."""

import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


class PasswordPolicyError(ValueError):
    """Raised when a password violates the security policy."""


def validate_password(password: str) -> None:
    """Validate a password without silently weakening policy."""
    errors: list[str] = []
    if len(password) < 12:
        errors.append("at least 12 characters")
    if len(password) > 128:
        errors.append("no more than 128 characters")
    if not re.search(r"[a-z]", password):
        errors.append("a lowercase letter")
    if not re.search(r"[A-Z]", password):
        errors.append("an uppercase letter")
    if not re.search(r"\d", password):
        errors.append("a number")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("a symbol")
    if errors:
        raise PasswordPolicyError("Password must contain " + ", ".join(errors))


def hash_password(password: str) -> str:
    """Validate and hash a password using Argon2id."""
    validate_password(password)
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a candidate password using constant-time Argon2 checks."""
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
