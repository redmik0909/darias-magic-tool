"""
Chiffrement des credentials Google avec mot de passe.
Le mot de passe est stocké dans le keyring Windows.
"""
import os
import base64
import keyring
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

APP_NAME    = "DariasMagicTool"
KEYRING_KEY = "google_creds_password"
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE  = os.path.join(BASE_DIR, "credentials.json")
ENC_FILE    = os.path.join(BASE_DIR, "credentials.enc")
SALT_FILE   = os.path.join(BASE_DIR, "credentials.salt")


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a Fernet key from a password + salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def encrypt_credentials(password: str) -> bool:
    """
    Encrypt credentials.json → credentials.enc using password.
    Returns True if successful.
    """
    if not os.path.exists(CREDS_FILE):
        return False

    salt = os.urandom(16)
    key  = _derive_key(password, salt)
    f    = Fernet(key)

    with open(CREDS_FILE, "rb") as fp:
        data = fp.read()

    encrypted = f.encrypt(data)

    with open(ENC_FILE, "wb") as fp:
        fp.write(encrypted)

    with open(SALT_FILE, "wb") as fp:
        fp.write(salt)

    # Store password in Windows keyring
    keyring.set_password(APP_NAME, KEYRING_KEY, password)

    return True


def decrypt_credentials() -> bytes | None:
    """
    Decrypt credentials.enc using password from keyring.
    Returns decrypted bytes or None if failed.
    """
    if not os.path.exists(ENC_FILE) or not os.path.exists(SALT_FILE):
        # Fallback — use plain credentials.json if exists
        if os.path.exists(CREDS_FILE):
            with open(CREDS_FILE, "rb") as fp:
                return fp.read()
        return None

    password = keyring.get_password(APP_NAME, KEYRING_KEY)
    if not password:
        return None

    with open(SALT_FILE, "rb") as fp:
        salt = fp.read()

    with open(ENC_FILE, "rb") as fp:
        encrypted = fp.read()

    try:
        key  = _derive_key(password, salt)
        f    = Fernet(key)
        return f.decrypt(encrypted)
    except Exception:
        return None


def decrypt_with_password(password: str) -> bytes | None:
    """Decrypt with a specific password (used for first-time setup)."""
    if not os.path.exists(ENC_FILE) or not os.path.exists(SALT_FILE):
        return None

    with open(SALT_FILE, "rb") as fp:
        salt = fp.read()

    with open(ENC_FILE, "rb") as fp:
        encrypted = fp.read()

    try:
        key = _derive_key(password, salt)
        f   = Fernet(key)
        return f.decrypt(encrypted)
    except Exception:
        return None


def is_setup_done() -> bool:
    """Check if credentials are encrypted and password is in keyring."""
    if not os.path.exists(ENC_FILE):
        return False
    password = keyring.get_password(APP_NAME, KEYRING_KEY)
    return password is not None


def setup_credentials(password: str) -> bool:
    """First-time setup — encrypt credentials.json."""
    return encrypt_credentials(password)