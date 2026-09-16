from __future__ import annotations

import base64
import hashlib
import os
import platform
from pathlib import Path


SERVICE_NAME = "betano-analyzer-oddspapi"
ENV_KEY = "ODDSPAPI_API_KEY"


def _config_dir() -> Path:
    override = os.getenv("BETANO_ANALYZER_CONFIG_DIR")
    if override:
        path = Path(override).expanduser()
    elif platform.system() == "Windows":
        path = Path(os.getenv("APPDATA", Path.home() / "AppData/Roaming")) / "BetanoAnalyzer"
    else:
        path = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "betano-analyzer"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _key_file() -> Path:
    return _config_dir() / "oddspapi.key"


def _protect(value: str) -> str:
    """Obfuscate the local key at rest; never use this as a replacement for OS secrets."""
    raw = value.encode("utf-8")
    mask = hashlib.sha256((platform.node() + SERVICE_NAME).encode()).digest()
    encoded = bytes(b ^ mask[i % len(mask)] for i, b in enumerate(raw))
    return base64.urlsafe_b64encode(encoded).decode("ascii")


def _unprotect(value: str) -> str:
    encoded = base64.urlsafe_b64decode(value.encode("ascii"))
    mask = hashlib.sha256((platform.node() + SERVICE_NAME).encode()).digest()
    raw = bytes(b ^ mask[i % len(mask)] for i, b in enumerate(encoded))
    return raw.decode("utf-8")


def save_api_key(api_key: str) -> None:
    key = api_key.strip()
    if not key:
        raise ValueError("api_key cannot be empty")
    path = _key_file()
    path.write_text(_protect(key), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_api_key() -> str | None:
    env_key = os.getenv(ENV_KEY, "").strip()
    if env_key:
        return env_key
    path = _key_file()
    if not path.exists():
        return None
    try:
        value = _unprotect(path.read_text(encoding="utf-8").strip())
        return value or None
    except (OSError, ValueError, UnicodeError):
        return None


def delete_api_key() -> None:
    try:
        _key_file().unlink()
    except FileNotFoundError:
        pass


def key_configured() -> bool:
    return bool(load_api_key())


def masked_api_key() -> str:
    key = load_api_key()
    if not key:
        return ""
    if len(key) <= 8:
        return "••••••••"
    return f"{key[:4]}{'•' * 8}{key[-4:]}"
