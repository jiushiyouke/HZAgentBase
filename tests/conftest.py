"""共享测试 fixtures。"""

import pytest
from pathlib import Path


@pytest.fixture
def tmp_memory_dir(tmp_path):
    """创建临时记忆目录，测试后自动清理。"""
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir()
    return mem_dir
