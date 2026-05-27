"""Permission settings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .modes import PermissionMode


@dataclass
class PermissionSettings:
    """Configuration for the permission system.

    Attributes:
        mode: Permission mode (DEFAULT, PLAN, FULL_AUTO).
        allowed_tools: Tools that are always allowed.
        denied_tools: Tools that are always denied.
        allowed_paths: Glob patterns for allowed file paths.
        denied_paths: Glob patterns for denied file paths.
        denied_commands: Shell command patterns that are denied.
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


# Sensitive paths that are always denied regardless of settings
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
