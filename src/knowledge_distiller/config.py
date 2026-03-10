"""Configuration management for knowledge-distiller."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import toml

CONFIG_DIR = Path.home() / ".config" / "knowledge-distiller"
CONFIG_FILE = CONFIG_DIR / "config.toml"

DEFAULTS: dict[str, Any] = {
    "provider": "google",
    "model": "gemini-2.5-flash",
    "language": None,
    "output_format": "markdown",
    "default_prompt": "",
    "transcriber": "mlx-whisper",
    "cache_dir": str(Path.home() / ".cache" / "knowledge-distiller"),
}

# Environment variable overrides (takes precedence over config file)
ENV_MAP = {
    "KD_PROVIDER": "provider",
    "KD_API_KEY": "api_key",
    "KD_MODEL": "model",
    "KD_LANGUAGE": "language",
    "KD_TRANSCRIBER": "transcriber",
}


def _load_file() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return toml.load(CONFIG_FILE)
    except Exception:
        return {}


def load() -> dict[str, Any]:
    """Return merged config: defaults < file < environment variables."""
    cfg = {**DEFAULTS, **_load_file()}
    for env_key, cfg_key in ENV_MAP.items():
        if value := os.environ.get(env_key):
            cfg[cfg_key] = value
    return cfg


def get(key: str, default: Any = None) -> Any:
    return load().get(key, default)


def set_value(key: str, value: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    cfg = _load_file()
    cfg[key] = value
    with open(CONFIG_FILE, "w") as f:
        toml.dump(cfg, f)


def get_api_key(provider: str | None = None) -> str | None:
    """Get API key: env var > keyring > config file."""
    if env_key := os.environ.get("KD_API_KEY"):
        return env_key

    p = provider or get("provider", "google")
    env_map = {
        "google": "GOOGLE_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    if alt_env := os.environ.get(env_map.get(p, "")):
        return alt_env

    try:
        import keyring
        key = keyring.get_password("knowledge-distiller", f"{p}_api_key")
        if key:
            return key
    except Exception:
        pass

    return _load_file().get("api_key")


def save_api_key(provider: str, api_key: str) -> None:
    try:
        import keyring
        keyring.set_password("knowledge-distiller", f"{provider}_api_key", api_key)
    except Exception:
        # Fallback: save to config file (less secure)
        set_value("api_key", api_key)
