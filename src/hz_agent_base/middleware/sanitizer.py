"""输出清洗中间件 — PII 过滤、敏感词、prompt 泄露检测。

功能：
- PII 遮盖：手机号、邮箱、身份证号、银行卡号
- 敏感词过滤：可配置的敏感词库
- Prompt 泄露检测：检测系统提示词是否被泄露

使用方式：
    from hz_agent_base.middleware.sanitizer import OutputSanitizerMiddleware

    agent = create_agent(
        middleware=[
            OutputSanitizerMiddleware(
                mask_pii=True,
                sensitive_words=["密码", "秘密"],
            )
        ]
    )
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Awaitable

from langchain.agents.middleware.types import AgentMiddleware

from ..sanitizer import MASK_FUNCTIONS

logger = logging.getLogger(__name__)


def load_sensitive_words_from_file(file_path: str | Path) -> set[str]:
    """从文件加载敏感词。

    支持两种格式：
    - .txt：每行一个词
    - .json：JSON 数组
    """
    path = Path(file_path)
    if not path.exists():
        logger.warning("Sensitive words file not found: %s", file_path)
        return set()

    content = path.read_text(encoding="utf-8")

    if path.suffix == ".json":
        try:
            words = json.loads(content)
            if isinstance(words, list):
                return set(words)
            else:
                logger.warning("JSON file should contain an array: %s", file_path)
                return set()
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON file %s: %s", file_path, e)
            return set()
    else:
        return set(line.strip() for line in content.splitlines() if line.strip())


def compute_text_hash(text: str) -> str:
    """计算文本的 SHA-256 哈希。"""
    return hashlib.sha256(text.encode()).hexdigest()


class OutputSanitizerMiddleware(AgentMiddleware):
    """输出清洗中间件。

    在模型调用后清洗输出，过滤敏感信息。

    Args:
        mask_pii: 是否遮盖 PII（手机号、邮箱、身份证、银行卡），默认 True。
        sensitive_words: 敏感词列表，直接传入。
        sensitive_words_file: 敏感词文件路径（.txt 或 .json）。
        detect_prompt_leak: 是否检测 prompt 泄露，默认 True。
        system_prompt_hash: 系统提示词的 SHA-256 哈希，用于检测泄露。
        custom_patterns: 自定义 PII 正则模式，格式为 {"name": pattern}。
        disable_patterns: 禁用的内置 PII 模式名称列表。
    """

    def __init__(
        self,
        mask_pii: bool = True,
        sensitive_words: list[str] | None = None,
        sensitive_words_file: str | None = None,
        detect_prompt_leak: bool = True,
        system_prompt_hash: str | None = None,
        custom_patterns: dict[str, str] | None = None,
        disable_patterns: list[str] | None = None,
    ):
        self.mask_pii = mask_pii
        self.detect_prompt_leak = detect_prompt_leak
        self.system_prompt_hash = system_prompt_hash

        # 构建 PII 遮盖函数列表
        self._mask_functions: list[tuple[str, Any]] = []
        if mask_pii:
            for name, func in MASK_FUNCTIONS.items():
                if disable_patterns and name in disable_patterns:
                    continue
                self._mask_functions.append((name, func))

            if custom_patterns:
                for name, pattern in custom_patterns.items():
                    compiled = re.compile(pattern)
                    def make_mask(regex):
                        def mask(text):
                            return regex.sub("***", text)
                        return mask
                    self._mask_functions.append((name, make_mask(compiled)))

        # 加载敏感词
        self.sensitive_words: set[str] = set()
        if sensitive_words:
            self.sensitive_words.update(sensitive_words)
        if sensitive_words_file:
            self.sensitive_words.update(load_sensitive_words_from_file(sensitive_words_file))

    def wrap_model_call(self, request, handler) -> Any:
        """调用模型后清洗输出。"""
        response = handler(request)

        messages = response.get("messages", []) if isinstance(response, dict) else []
        for msg in messages:
            content = getattr(msg, "content", None)
            if content and isinstance(content, str):
                cleaned = self._sanitize(content, request)
                if cleaned != content:
                    msg.content = cleaned

        return response

    async def awrap_model_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        """调用模型后清洗输出（异步版本）。"""
        response = await handler(request)

        messages = response.get("messages", []) if isinstance(response, dict) else []
        for msg in messages:
            content = getattr(msg, "content", None)
            if content and isinstance(content, str):
                cleaned = self._sanitize(content, request)
                if cleaned != content:
                    msg.content = cleaned

        return response

    def _sanitize(self, text: str, request: Any) -> str:
        """清洗文本。"""
        if self._mask_functions:
            text = self._mask_pii(text)

        if self.sensitive_words:
            text = self._filter_sensitive_words(text)

        if self.detect_prompt_leak and self.system_prompt_hash:
            self._check_prompt_leak(text, request)

        return text

    def _mask_pii(self, text: str) -> str:
        """遮盖 PII 信息。"""
        for name, func in self._mask_functions:
            text = func(text)
        return text

    def _filter_sensitive_words(self, text: str) -> str:
        """过滤敏感词，替换为 *。"""
        for word in self.sensitive_words:
            if word in text:
                replacement = "*" * len(word)
                text = text.replace(word, replacement)
        return text

    def _check_prompt_leak(self, text: str, request: Any) -> None:
        """检测 prompt 泄露。"""
        if not self.system_prompt_hash:
            return

        if self.system_prompt_hash in text:
            logger.warning(
                "Potential prompt leak detected: system prompt hash found in output"
            )
            return

        system_prompt = getattr(request, "system_prompt", "")
        if system_prompt and len(system_prompt) > 50:
            mid = len(system_prompt) // 2
            fragment = system_prompt[mid - 25:mid + 25]
            if fragment in text:
                logger.warning(
                    "Potential prompt leak detected: system prompt fragment found in output"
                )
