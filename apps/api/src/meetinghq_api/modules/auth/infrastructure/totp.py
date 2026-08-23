"""TOTP primitives for account-level multi-factor authentication."""

import base64
import hmac
import secrets
import struct
import time
from hashlib import sha1
from urllib.parse import quote


def create_totp_secret() -> str:
    """Return a base32 secret suitable for authenticator apps."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def provisioning_uri(secret: str, issuer: str, account_name: str) -> str:
    """Build an otpauth URI without exposing implementation details to clients."""
    label = f"{issuer}:{account_name}"
    return (
        "otpauth://totp/"
        f"{quote(label)}?secret={quote(secret)}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"
    )


def generate_totp(secret: str, timestamp: int | None = None, period: int = 30) -> str:
    """Generate a six-digit TOTP code for the supplied timestamp."""
    padded = secret.upper() + ("=" * ((8 - len(secret) % 8) % 8))
    key = base64.b32decode(padded, casefold=True)
    counter = int((timestamp if timestamp is not None else time.time()) // period)
    digest = hmac.new(key, struct.pack(">Q", counter), sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{code % 1_000_000:06d}"


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    """Validate a user supplied code with a small clock-skew window."""
    normalized = "".join(character for character in code if character.isdigit())
    if len(normalized) != 6:
        return False
    now = int(time.time())
    return any(
        hmac.compare_digest(generate_totp(secret, now + (offset * 30)), normalized)
        for offset in range(-window, window + 1)
    )
