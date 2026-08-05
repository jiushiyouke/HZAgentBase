"""Configuration loader - reads from .env file.

统一配置 MODEL_API_KEY / MODEL_BASE_URL，通过 DEFAULT_MODEL 的值自动匹配提供商。
安全特性：API Key 空值警告、HTTP 协议警告。

使用懒加载：import 时不会读取 .env，第一次访问配置变量时才加载。
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
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
        load_dotenv(env_path, override=False)

    return {
        # 模型配置
        "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL", "deepseek-v4-flash"),
        "MODEL_API_KEY": os.environ.get("MODEL_API_KEY", ""),
        "MODEL_BASE_URL": os.environ.get("MODEL_BASE_URL", ""),
        # 容错配置
        "MODEL_REQUEST_TIMEOUT": os.environ.get("MODEL_REQUEST_TIMEOUT", "600"),
        "MODEL_MAX_RETRIES": os.environ.get("MODEL_MAX_RETRIES", "2"),
        "RECURSION_LIMIT": os.environ.get("RECURSION_LIMIT", "25"),
        # 权限
        "PERMISSION_MODE": os.environ.get("PERMISSION_MODE", "default"),
        # 记忆
        "MEMORY_PATH": os.environ.get("MEMORY_PATH", ".memory"),
        "MEMORY_CACHE_SIZE": os.environ.get("MEMORY_CACHE_SIZE", "100"),
        "MEMORY_CACHE_TTL": os.environ.get("MEMORY_CACHE_TTL", "300"),
        # 文件锁分片数
        "FILE_LOCK_SHARDS": os.environ.get("FILE_LOCK_SHARDS", "64"),
        # 文件审计
        "AUDIT_LOG_PATH": os.environ.get("AUDIT_LOG_PATH", ".audit/audit.jsonl"),
        # 知识库
        "KNOWLEDGE_TOP_K": os.environ.get("KNOWLEDGE_TOP_K", "5"),
        # 日志
        "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO"),
    }


@lru_cache(maxsize=1)
def _get_config() -> dict[str, str]:
    """获取配置（懒加载，只执行一次）。"""
    config = load_config()

    # 安全警告
    if not config["MODEL_API_KEY"]:
        logger.warning("MODEL_API_KEY is not set. API calls will fail for cloud models (DeepSeek, OpenAI, Anthropic, Gemini).")

    if config["MODEL_BASE_URL"] and config["MODEL_BASE_URL"].startswith("http://"):
        logger.warning("MODEL_BASE_URL uses HTTP (not HTTPS). API keys will be transmitted in plaintext: %s", config["MODEL_BASE_URL"])

    # 应用日志级别配置
    logging.basicConfig(level=config["LOG_LEVEL"])

    return config


# 配置属性名到类型的映射（int 类型需要转换）
_INT_KEYS = {
    "KNOWLEDGE_TOP_K", "MODEL_REQUEST_TIMEOUT", "MODEL_MAX_RETRIES", "RECURSION_LIMIT",
    "MEMORY_CACHE_SIZE", "MEMORY_CACHE_TTL", "FILE_LOCK_SHARDS",
}

# 所有有效的配置属性名
_VALID_KEYS = set(load_config.__code__.co_consts) - {None}


def __getattr__(name: str):
    """模块级懒加载：第一次访问配置变量时才读取 .env。"""
    _config = _get_config()
    if name in _config:
        value = _config[name]
        if name in _INT_KEYS:
            return int(value)
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
