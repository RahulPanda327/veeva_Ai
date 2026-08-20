"""
Password hashing utilities.

verify_password() accepts either a bcrypt hash or a plaintext value in the
config so existing setups keep working — but logs a one-time warning when
plaintext is detected, with a hint to switch.

CLI helper (run from project root):
    python -m auth.password mySecretPassword123
prints a bcrypt hash you can paste into .env as ADMIN_PASSWORD.
"""

from passlib.context import CryptContext

from utils.logging_util import setup_logging

logger = setup_logging("password")

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")

_plaintext_warned = False


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def is_bcrypt_hash(stored: str) -> bool:
    return bool(stored) and stored.startswith(_BCRYPT_PREFIXES)


def verify_password(plain: str, stored: str) -> bool:
    """Compare a plaintext password against a stored hash or plaintext value."""
    global _plaintext_warned
    if not stored:
        return False

    if is_bcrypt_hash(stored):
        try:
            return _pwd_ctx.verify(plain, stored)
        except Exception:
            return False

    # Plaintext fallback — emit a single warning per process
    if not _plaintext_warned:
        logger.warning({
            "event": "plaintext_password_in_use",
            "hint": "Generate a bcrypt hash via: python -m auth.password <password>",
        })
        _plaintext_warned = True
    return plain == stored


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m auth.password <password>", file=sys.stderr)
        sys.exit(2)
    print(hash_password(sys.argv[1]))
