"""Configuration loader - reads from .env file.

统一配置 MODEL_API_KEY / MODEL_BASE_URL，通过 DEFAULT_MODEL 的值自动匹配提供商。
安全特性：API Key 空值警告、HTTP 协议警告。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


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
        # 模型配置
        "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL", "deepseek-v4-flash"),
        "MODEL_API_KEY": os.environ.get("MODEL_API_KEY", ""),
        "MODEL_BASE_URL": os.environ.get("MODEL_BASE_URL", ""),
        # 权限
        "PERMISSION_MODE": os.environ.get("PERMISSION_MODE", "default"),
        # 记忆
        "MEMORY_PATH": os.environ.get("MEMORY_PATH", ".memory"),
        # 文件审计
        "AUDIT_LOG_PATH": os.environ.get("AUDIT_LOG_PATH", ".audit/audit.jsonl"),
        # 知识库
        "KNOWLEDGE_TOP_K": os.environ.get("KNOWLEDGE_TOP_K", "5"),
        # 日志
        "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO"),
    }


# Auto-load on import
_config = load_config()

DEFAULT_MODEL = _config["DEFAULT_MODEL"]
MODEL_API_KEY = _config["MODEL_API_KEY"]
MODEL_BASE_URL = _config["MODEL_BASE_URL"]

PERMISSION_MODE = _config["PERMISSION_MODE"]
MEMORY_PATH = _config["MEMORY_PATH"]
AUDIT_LOG_PATH = _config["AUDIT_LOG_PATH"]
KNOWLEDGE_TOP_K = int(_config["KNOWLEDGE_TOP_K"])
LOG_LEVEL = _config["LOG_LEVEL"]

# 安全警告
if not MODEL_API_KEY:
    logger.warning("MODEL_API_KEY is not set. API calls will fail for cloud models (DeepSeek, OpenAI, Anthropic, Gemini).")

if MODEL_BASE_URL and MODEL_BASE_URL.startswith("http://"):
    logger.warning("MODEL_BASE_URL uses HTTP (not HTTPS). API keys will be transmitted in plaintext: %s", MODEL_BASE_URL)
