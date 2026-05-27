"""测试提示词管理：PromptManager、load_prompt。"""

import pytest
from pathlib import Path

from hz_agent_base.prompts.manager import PromptManager, load_prompt


# ============================================================
# PromptManager 测试
# ============================================================

class TestPromptManager:
    """测试 PromptManager 从目录加载提示词。"""

    def test_load_base_md(self, tmp_path):
        """应加载 base.md 作为基础提示词。"""
        base = tmp_path / "base.md"
        base.write_text("你是一个助手。", encoding="utf-8")

        pm = PromptManager(tmp_path)
        result = pm.build()
        assert result == "你是一个助手。"

    def test_load_rules_in_order(self, tmp_path):
        """rules/ 下的 .md 文件应按文件名字母序加载。"""
        base = tmp_path / "base.md"
        base.write_text("基础人设", encoding="utf-8")

        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "b_format.md").write_text("格式规则", encoding="utf-8")
        (rules_dir / "a_safety.md").write_text("安全规则", encoding="utf-8")

        pm = PromptManager(tmp_path)
        result = pm.build()

        # 安全规则（a_）应在格式规则（b_）之前
        assert result.index("安全规则") < result.index("格式规则")

    def test_shared_rules_appended(self, tmp_path):
        """共享规则应追加到 agent 规则之后。"""
        base = tmp_path / "base.md"
        base.write_text("基础人设", encoding="utf-8")

        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "agent_rule.md").write_text("Agent 规则", encoding="utf-8")

        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()
        (shared_dir / "shared_rule.md").write_text("共享规则", encoding="utf-8")

        pm = PromptManager(tmp_path, shared_rules=[shared_dir])
        result = pm.build()

        # Agent 规则应在共享规则之前
        assert result.index("Agent 规则") < result.index("共享规则")

    def test_no_base_md(self, tmp_path):
        """没有 base.md 时应只加载规则。"""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "rule.md").write_text("某条规则", encoding="utf-8")

        pm = PromptManager(tmp_path)
        result = pm.build()
        assert result == "某条规则"

    def test_empty_directory(self, tmp_path):
        """空目录应返回空字符串。"""
        pm = PromptManager(tmp_path)
        result = pm.build()
        assert result == ""

    def test_rules_dir_not_exist(self, tmp_path):
        """rules/ 目录不存在时不应报错。"""
        base = tmp_path / "base.md"
        base.write_text("基础人设", encoding="utf-8")

        pm = PromptManager(tmp_path)
        result = pm.build()
        assert result == "基础人设"

    def test_skips_non_md_files_in_rules(self, tmp_path):
        """rules/ 下的非 .md 文件应被忽略。"""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "rule.md").write_text("规则内容", encoding="utf-8")
        (rules_dir / "notes.txt").write_text("这不是规则", encoding="utf-8")

        pm = PromptManager(tmp_path)
        result = pm.build()
        assert "规则内容" in result
        assert "这不是规则" not in result

    def test_multiple_shared_rule_dirs(self, tmp_path):
        """应支持多个共享规则目录。"""
        base = tmp_path / "base.md"
        base.write_text("基础", encoding="utf-8")

        shared1 = tmp_path / "shared1"
        shared1.mkdir()
        (shared1 / "rule1.md").write_text("规则1", encoding="utf-8")

        shared2 = tmp_path / "shared2"
        shared2.mkdir()
        (shared2 / "rule2.md").write_text("规则2", encoding="utf-8")

        pm = PromptManager(tmp_path, shared_rules=[shared1, shared2])
        result = pm.build()
        assert "规则1" in result
        assert "规则2" in result


class TestPromptManagerFromFile:
    """测试 from_file 类方法。"""

    def test_from_single_file(self, tmp_path):
        """从单个文件创建应加载该文件内容。"""
        f = tmp_path / "my_prompt.md"
        f.write_text("自定义提示词", encoding="utf-8")

        pm = PromptManager.from_file(f)
        result = pm.build()
        assert result == "自定义提示词"

    def test_from_file_with_shared_rules(self, tmp_path):
        """from_file 应支持叠加共享规则。"""
        f = tmp_path / "base.md"
        f.write_text("基础提示", encoding="utf-8")

        shared = tmp_path / "shared"
        shared.mkdir()
        (shared / "rule.md").write_text("共享规则", encoding="utf-8")

        pm = PromptManager.from_file(f, shared_rules=[shared])
        result = pm.build()
        assert "基础提示" in result
        assert "共享规则" in result


# ============================================================
# load_prompt 便捷函数测试
# ============================================================

class TestLoadPrompt:
    """测试 load_prompt 便捷函数。"""

    def test_none_returns_empty(self):
        """None 应返回空字符串。"""
        assert load_prompt(None) == ""

    def test_plain_string_returned_as_is(self):
        """普通字符串应原样返回。"""
        assert load_prompt("你是一个助手") == "你是一个助手"

    def test_directory_path(self, tmp_path):
        """目录路径应通过 PromptManager 加载。"""
        base = tmp_path / "base.md"
        base.write_text("目录提示词", encoding="utf-8")

        result = load_prompt(tmp_path)
        assert result == "目录提示词"

    def test_file_path(self, tmp_path):
        """文件路径应通过 PromptManager 加载。"""
        f = tmp_path / "prompt.md"
        f.write_text("文件提示词", encoding="utf-8")

        result = load_prompt(f)
        assert result == "文件提示词"

    def test_nonexistent_path_returns_string(self):
        """不存在的路径应原样返回字符串。"""
        result = load_prompt("./not/exist.md")
        assert result == "./not/exist.md"

    def test_with_shared_rules(self, tmp_path):
        """应支持叠加共享规则。"""
        base = tmp_path / "base.md"
        base.write_text("基础", encoding="utf-8")

        shared = tmp_path / "shared"
        shared.mkdir()
        (shared / "rule.md").write_text("共享规则", encoding="utf-8")

        result = load_prompt(tmp_path, shared_rules=[shared])
        assert "基础" in result
        assert "共享规则" in result
