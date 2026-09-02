"""
Short code generation and validation.
Auto-generated codes use a URL-safe alphabet with no ambiguous characters
(no 0/O, no 1/l/I) so codes stay easy to read and share out loud.
"""

import re
import secrets

ALPHABET = "23456789abcdefghjkmnpqrstuvwxyzACDEFGHJKLMNPQRSTUVWXYZ"
CUSTOM_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def generate_code(length: int) -> str:
    """Cryptographically random short code from the safe alphabet."""
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def is_valid_custom_code(code: str) -> bool:
    """Custom codes: letters, digits, underscore, hyphen only."""
    return bool(CUSTOM_CODE_PATTERN.match(code))


RESERVED_CODES = {"api", "dashboard", "login", "logout", "static", "health", "new"}


def is_reserved(code: str) -> bool:
    return code.lower() in RESERVED_CODES
