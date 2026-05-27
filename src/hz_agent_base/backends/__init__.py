"""Backends package - pluggable filesystem/sandbox backends."""

# Re-export Deep Agents backends（版本兼容保护）
try:
    from deepagents.backends import (
        BackendProtocol,
        SandboxBackendProtocol,
        FilesystemBackend,
        LocalShellBackend,
        StateBackend,
    )
    __all__ = [
        "BackendProtocol",
        "SandboxBackendProtocol",
        "FilesystemBackend",
        "LocalShellBackend",
        "StateBackend",
    ]
except ImportError:
    # deepagents 版本升级可能导致部分类移除或重命名
    # 提供最小可用集合，避免导入整个包时报错
    from deepagents.backends import BackendProtocol
    __all__ = ["BackendProtocol"]
