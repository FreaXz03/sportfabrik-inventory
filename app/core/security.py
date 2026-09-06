"""Passwort-Hashing für Chef-Konten. Bewusst ohne zusätzliche Abhängigkeit:
PBKDF2-HMAC-SHA256 aus der Python-Standardbibliothek, mit Salt pro Passwort.
"""
import hashlib
import hmac
import secrets

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    """Erzeugt einen selbstbeschreibenden Hash: algorithmus$iterationen$salt$hash (alles hex)."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Vergleicht zeitkonstant gegen einen mit hash_password() erzeugten Hash."""
    try:
        algorithm, iterations, salt, expected_hex = stored_hash.split("$")
        if algorithm != _ALGORITHM:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(digest.hex(), expected_hex)
    except (ValueError, AttributeError):
        return False
