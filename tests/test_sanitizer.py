"""测试输出清洗中间件 OutputSanitizerMiddleware。"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from langchain_core.messages import HumanMessage, AIMessage

from hz_agent_base.middleware.sanitizer import OutputSanitizerMiddleware, load_sensitive_words_from_file, compute_text_hash
from hz_agent_base.sanitizer import mask_phone, mask_email, mask_id_card, mask_bank_card


# ============================================================
# 辅助函数
# ============================================================

def make_mock_request(messages=None, system_prompt="You are helpful."):
    """创建一个模拟的 ModelRequest 对象。"""
    request = MagicMock()
    request.messages = messages or [HumanMessage(content="hello")]
    request.system_prompt = system_prompt
    return request


def make_mock_response(content: str):
    """创建一个模拟的响应。"""
    msg = AIMessage(content=content)
    return {"messages": [msg]}


# ============================================================
# PII 遮盖函数测试
# ============================================================

class TestMaskPhone:
    """测试手机号遮盖。"""

    def test_mask_chinese_phone(self):
        assert mask_phone("13812345678") == "138****5678"

    def test_mask_phone_in_text(self):
        text = "请联系我，手机号13812345678，谢谢"
        expected = "请联系我，手机号138****5678，谢谢"
        assert mask_phone(text) == expected

    def test_mask_multiple_phones(self):
        text = "13812345678 和 15987654321"
        expected = "138****5678 和 159****4321"
        assert mask_phone(text) == expected

    def test_no_phone(self):
        text = "没有手机号"
        assert mask_phone(text) == text


class TestMaskEmail:
    """测试邮箱遮盖。"""

    def test_mask_email(self):
        assert mask_email("test@example.com") == "t***@example.com"

    def test_mask_email_in_text(self):
        text = "发送到 test@example.com 即可"
        expected = "发送到 t***@example.com 即可"
        assert mask_email(text) == expected

    def test_mask_short_local(self):
        assert mask_email("a@b.com") == "*@b.com"

    def test_no_email(self):
        text = "没有邮箱"
        assert mask_email(text) == text


class TestMaskIdCard:
    """测试身份证号遮盖。"""

    def test_mask_id_card(self):
        assert mask_id_card("110101199001011234") == "110***********1234"

    def test_mask_id_card_in_text(self):
        text = "身份证号110101199001011234"
        expected = "身份证号110***********1234"
        assert mask_id_card(text) == expected

    def test_no_id_card(self):
        text = "没有身份证号"
        assert mask_id_card(text) == text


class TestMaskBankCard:
    """测试银行卡号遮盖。"""

    def test_mask_bank_card(self):
        assert mask_bank_card("6222021234567890123") == "6222 **** **** 0123"

    def test_mask_bank_card_16(self):
        assert mask_bank_card("6222021234567890") == "6222 **** **** 7890"

    def test_no_bank_card(self):
        text = "没有银行卡号"
        assert mask_bank_card(text) == text


# ============================================================
# 敏感词文件加载测试
# ============================================================

class TestLoadSensitiveWords:
    """测试敏感词文件加载。"""

    def test_load_txt_file(self, tmp_path):
        """测试加载 .txt 文件。"""
        file_path = tmp_path / "words.txt"
        file_path.write_text("密码\n秘密\n内部\n", encoding="utf-8")

        words = load_sensitive_words_from_file(file_path)
        assert words == {"密码", "秘密", "内部"}

    def test_load_json_file(self, tmp_path):
        """测试加载 .json 文件。"""
        file_path = tmp_path / "words.json"
        file_path.write_text(json.dumps(["密码", "秘密", "内部"]), encoding="utf-8")

        words = load_sensitive_words_from_file(file_path)
        assert words == {"密码", "秘密", "内部"}

    def test_load_empty_lines(self, tmp_path):
        """测试加载包含空行的文件。"""
        file_path = tmp_path / "words.txt"
        file_path.write_text("密码\n\n秘密\n\n", encoding="utf-8")

        words = load_sensitive_words_from_file(file_path)
        assert words == {"密码", "秘密"}

    def test_load_nonexistent_file(self):
        """测试加载不存在的文件。"""
        words = load_sensitive_words_from_file("/nonexistent/file.txt")
        assert words == set()

    def test_load_invalid_json(self, tmp_path):
        """测试加载无效 JSON 文件。"""
        file_path = tmp_path / "invalid.json"
        file_path.write_text("not json", encoding="utf-8")

        words = load_sensitive_words_from_file(file_path)
        assert words == set()


# ============================================================
# 工具函数测试
# ============================================================

class TestComputeTextHash:
    """测试文本哈希计算。"""

    def test_hash_consistency(self):
        """相同文本应产生相同哈希。"""
        h1 = compute_text_hash("hello")
        h2 = compute_text_hash("hello")
        assert h1 == h2

    def test_hash_different(self):
        """不同文本应产生不同哈希。"""
        h1 = compute_text_hash("hello")
        h2 = compute_text_hash("world")
        assert h1 != h2

    def test_hash_format(self):
        """哈希应为 64 字符的十六进制字符串。"""
        h = compute_text_hash("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ============================================================
# OutputSanitizerMiddleware 测试
# ============================================================

class TestOutputSanitizerMiddleware:
    """测试输出清洗中间件。"""

    def test_mask_pii_phone(self):
        """测试 PII 遮盖 - 手机号。"""
        mw = OutputSanitizerMiddleware(mask_pii=True)
        request = make_mock_request()
        response = make_mock_response("手机号13812345678")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        assert "138****5678" in result["messages"][0].content

    def test_mask_pii_email(self):
        """测试 PII 遮盖 - 邮箱。"""
        mw = OutputSanitizerMiddleware(mask_pii=True)
        request = make_mock_request()
        response = make_mock_response("邮箱test@example.com")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        assert "t***@example.com" in result["messages"][0].content

    def test_mask_pii_disabled(self):
        """测试禁用 PII 遮盖。"""
        mw = OutputSanitizerMiddleware(mask_pii=False)
        request = make_mock_request()
        response = make_mock_response("手机号13812345678")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        assert "13812345678" in result["messages"][0].content

    def test_sensitive_words_filter(self):
        """测试敏感词过滤。"""
        mw = OutputSanitizerMiddleware(sensitive_words=["密码", "秘密"])
        request = make_mock_request()
        response = make_mock_response("这是密码，那是秘密")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        content = result["messages"][0].content
        assert "密码" not in content
        assert "秘密" not in content
        assert "**" in content

    def test_sensitive_words_from_file(self, tmp_path):
        """测试从文件加载敏感词。"""
        file_path = tmp_path / "words.txt"
        file_path.write_text("密码\n秘密\n", encoding="utf-8")

        mw = OutputSanitizerMiddleware(sensitive_words_file=str(file_path))
        request = make_mock_request()
        response = make_mock_response("这是密码")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        assert "密码" not in result["messages"][0].content

    def test_sensitive_words_combined(self, tmp_path):
        """测试直接传入 + 文件加载。"""
        file_path = tmp_path / "words.txt"
        file_path.write_text("密码\n", encoding="utf-8")

        mw = OutputSanitizerMiddleware(
            sensitive_words=["秘密"],
            sensitive_words_file=str(file_path),
        )
        assert "密码" in mw.sensitive_words
        assert "秘密" in mw.sensitive_words

    def test_prompt_leak_detection(self):
        """测试 prompt 泄露检测。"""
        system_prompt = "This is a very long system prompt for testing purposes only"
        prompt_hash = compute_text_hash(system_prompt)

        mw = OutputSanitizerMiddleware(
            detect_prompt_leak=True,
            system_prompt_hash=prompt_hash,
        )
        request = make_mock_request(system_prompt=system_prompt)
        response = make_mock_response(f"hash is {prompt_hash}")
        handler = MagicMock(return_value=response)

        # 应该记录警告但不修改内容
        result = mw.wrap_model_call(request, handler)
        assert prompt_hash in result["messages"][0].content

    def test_custom_patterns(self):
        """测试自定义 PII 模式。"""
        mw = OutputSanitizerMiddleware(
            mask_pii=True,
            custom_patterns={"custom_id": r"USER-\d{6}"},
        )
        request = make_mock_request()
        response = make_mock_response("用户ID: USER-123456")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        assert "USER-123456" not in result["messages"][0].content

    def test_disable_patterns(self):
        """测试禁用内置 PII 模式。"""
        mw = OutputSanitizerMiddleware(
            mask_pii=True,
            disable_patterns=["phone"],
        )
        request = make_mock_request()
        response = make_mock_response("手机号13812345678，邮箱test@example.com")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        content = result["messages"][0].content
        # 手机号不应被遮盖
        assert "13812345678" in content
        # 邮箱应被遮盖
        assert "test@example.com" not in content


# ============================================================
# 集成测试
# ============================================================

class TestIntegration:
    """集成测试。"""

    def test_create_agent_with_sanitizer(self):
        """测试 create_agent 集成。"""
        from hz_agent_base import create_agent
        from hz_agent_base.middleware.sanitizer import OutputSanitizerMiddleware

        agent = create_agent(
            model="deepseek-v4-flash",
            middleware=[
                OutputSanitizerMiddleware(mask_pii=True)
            ],
        )
        assert agent is not None

    def test_priority_constant_exists(self):
        """测试优先级常量存在。"""
        from hz_agent_base.utils.constants import SANITIZER
        assert SANITIZER == 33

    def test_middleware_exported(self):
        """测试中间件被正确导出。"""
        from hz_agent_base.middleware import OutputSanitizerMiddleware
        assert OutputSanitizerMiddleware is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
