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
        r"rm\s+-rf?\s+/",           # rm -rf /
        r"rm\s+-rf?\s+/\*",         # rm -rf /*
        r"mkfs",                     # mkfs（格式化磁盘）
        r"dd\s+if=",                # dd if=（磁盘写入）
        r":\(\)\{.*:\|:.*\};:",     # fork bomb
        r"curl\s.*\|\s*(ba)?sh",    # curl | sh（远程代码执行）
        r"wget\s.*\|\s*(ba)?sh",    # wget | sh
        r"chmod\s+777",             # chmod 777（过度开放权限）
        r"\bnc\b.*-e",              # netcat 反弹 shell
        r"python[3]?\s+-c.*import\s+os.*system",  # python 一行命令执行
        r"eval\s+",                 # eval
        r"exec\s+",                 # exec
        r"mkfifo",                  # mkfifo（创建命名管道，常用于反弹 shell）
    ])


# 敏感路径列表 — 无论权限设置如何，始终拒绝访问
# 包含 SSH 密钥、云服务凭证、环境变量文件、私钥等
SENSITIVE_PATH_PATTERNS = [
    # SSH 密钥
    "~/.ssh/*",
    "**/id_rsa",
    "**/id_ed25519",
    "**/id_ecdsa",
    "**/id_dsa",
    # 云服务凭证
    "~/.aws/*",
    "~/.gcloud/*",
    "~/.azure/*",
    "~/.config/gcloud/*",
    # GPG / Docker / Kubernetes
    "~/.gnupg/*",
    "~/.docker/config.json",
    "~/.kube/config",
    # 包管理器凭证
    "~/.netrc",
    "~/.npmrc",
    "~/.pypirc",
    # 环境变量和密钥文件
    "**/.env",
    "**/.env.*",
    "**/credentials",
    "**/credentials.json",
    "**/secrets.json",
    "**/service-account.json",
    # 证书和私钥
    "**/*.pem",
    "**/*.key",
    "**/*.p12",
    "**/*.pfx",
]
