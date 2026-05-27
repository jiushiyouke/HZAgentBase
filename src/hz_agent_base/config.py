"""Configuration loader - reads from .env file."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv


def load_config(env_path: str | Path | None = None) -> dict[str, str]:
    """Load configuration from .env file.

    Args:
        env_path: Path to .env file. If None, searches from cwd upward.

    Returns:
        Dictionary of configuration values.
    """
    if env_path is None:
        # Search for .env from current directory upward
        current = Path.cwd()
        while current != current.parent:
            candidate = current / ".env"
            if candidate.exists():
                env_path = candidate
                break
            current = current.parent
    else:
        env_path = Path(env_path)

    # Load .env file
    if env_path and Path(env_path).exists():
        load_dotenv(env_path, override=True)

    return {
        "DEEPSEEK_API_KEY": os.environ.get("DEEPSEEK_API_KEY", ""),
        "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL", "deepseek-v4-flash"),
        "DEEPSEEK_BASE_URL": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        "PERMISSION_MODE": os.environ.get("PERMISSION_MODE", "default"),
        "MEMORY_PATH": os.environ.get("MEMORY_PATH", ".memory"),
        "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO"),
    }


# Auto-load on import
_config = load_config()

DEEPSEEK_API_KEY = _config["DEEPSEEK_API_KEY"]
DEFAULT_MODEL = _config["DEFAULT_MODEL"]
DEEPSEEK_BASE_URL = _config["DEEPSEEK_BASE_URL"]
PERMISSION_MODE = _config["PERMISSION_MODE"]
MEMORY_PATH = _config["MEMORY_PATH"]
LOG_LEVEL = _config["LOG_LEVEL"]
