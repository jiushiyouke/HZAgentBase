"""权限配置数据类和敏感路径定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .modes import PermissionMode


@dataclass
class PermissionSettings:
    """权限系统配置。

    Attributes:
        mode: 权限模式（DEFAULT / PLAN / FULL_AUTO）。
        allowed_tools: 始终允许的工具白名单。为空表示不限制。
        denied_tools: 始终拒绝的工具黑名单。
        allowed_paths: 允许访问的文件路径 glob 模式。
        denied_paths: 拒绝访问的文件路径 glob 模式。
        denied_commands: 拒绝执行的 shell 命令模式（子串匹配）。
    """

    mode: PermissionMode = PermissionMode.DEFAULT
    allowed_tools: list[str] = field(default_factory=list)
    denied_tools: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)
    denied_paths: list[str] = field(default_factory=list)
    denied_commands: list[str] = field(default_factory=lambda: [
        "rm -rf /",
        "rm -rf /*",
        "mkfs",
        "dd if=",
        ":(){:|:&};:",  # fork bomb
    ])


# 敏感路径列表 — 无论权限设置如何，始终拒绝访问
# 包含 SSH 密钥、云服务凭证、环境变量文件、私钥等
SENSITIVE_PATH_PATTERNS = [
    "~/.ssh/*",
    "~/.aws/*",
    "~/.gcloud/*",
    "~/.azure/*",
    "~/.gnupg/*",
    "~/.docker/config.json",
    "~/.kube/config",
    "~/.netrc",
    "~/.npmrc",
    "~/.pypirc",
    "**/.env",
    "**/.env.*",
    "**/credentials",
    "**/credentials.json",
    "**/secrets.json",
    "**/id_rsa",
    "**/id_ed25519",
    "**/*.pem",
    "**/*.key",
]
