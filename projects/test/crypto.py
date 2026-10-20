"""Quản lý Fernet key để mã hoá mật khẩu trong DB."""
import os
from cryptography.fernet import Fernet

from config import FERNET_KEY_FILE


def _load_or_create_fernet_key() -> bytes:
    if os.path.exists(FERNET_KEY_FILE):
        with open(FERNET_KEY_FILE, "rb") as f:
            return f.read().strip()
    key = Fernet.generate_key()
    with open(FERNET_KEY_FILE, "wb") as f:
        f.write(key)
    try:
        os.chmod(FERNET_KEY_FILE, 0o600)
    except Exception:
        pass
    return key


FERNET_KEY = _load_or_create_fernet_key()
fernet = Fernet(FERNET_KEY)