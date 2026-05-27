"""测试配置加载模块。"""

import os
from pathlib import Path
from unittest.mock import patch

from hz_agent_base.config import load_config


class TestLoadConfig:
    """测试 load_config 函数。"""

    def test_returns_dict_with_expected_keys(self, tmp_path):
        """确保返回的配置包含所有必要字段。"""
        env_file = tmp_path / ".env"
        env_file.write_text("DEEPSEEK_API_KEY=test-key\n", encoding="utf-8")

        config = load_config(env_path=env_file)

        assert "DEEPSEEK_API_KEY" in config
        assert "DEFAULT_MODEL" in config
        assert "DEEPSEEK_BASE_URL" in config
        assert "PERMISSION_MODE" in config
        assert "MEMORY_PATH" in config
        assert "LOG_LEVEL" in config

    def test_reads_values_from_env_file(self, tmp_path):
        """确保能正确读取 .env 文件中的值。"""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "DEEPSEEK_API_KEY=sk-test123\nDEFAULT_MODEL=my-model\n",
            encoding="utf-8",
        )

        config = load_config(env_path=env_file)

        assert config["DEEPSEEK_API_KEY"] == "sk-test123"
        assert config["DEFAULT_MODEL"] == "my-model"

    def test_defaults_when_no_env_file(self, tmp_path):
        """没有 .env 文件时应返回默认值。"""
        # 清除可能被前一个测试污染的环境变量
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("DEEPSEEK_API_KEY", "DEFAULT_MODEL", "DEEPSEEK_BASE_URL",
                                  "PERMISSION_MODE", "MEMORY_PATH", "LOG_LEVEL")}
        with patch.dict(os.environ, clean_env, clear=True):
            config = load_config(env_path=tmp_path / "nonexistent.env")

            assert config["DEFAULT_MODEL"] == "deepseek-v4-flash"
            assert config["DEEPSEEK_BASE_URL"] == "https://api.deepseek.com/v1"
            assert config["PERMISSION_MODE"] == "default"

    def test_env_file_overrides_os_env(self, tmp_path):
        """确保 .env 文件覆盖 os.environ 的值。"""
        env_file = tmp_path / ".env"
        env_file.write_text("DEEPSEEK_API_KEY=from-file\n", encoding="utf-8")

        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "from-env"}):
            config = load_config(env_path=env_file)

        assert config["DEEPSEEK_API_KEY"] == "from-file"
