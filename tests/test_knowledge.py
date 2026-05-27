"""测试知识库协议和 KnowledgeMiddleware。"""

import pytest
from unittest.mock import MagicMock
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, AIMessage

from hz_agent_base.knowledge.protocol import Retriever, RetrievalResult
from hz_agent_base.middleware.knowledge import KnowledgeMiddleware, _format_results


# ============================================================
# 辅助：构造 mock 对象
# ============================================================

def make_mock_retriever(results=None):
    """创建一个模拟 Retriever。"""
    retriever = MagicMock(spec=Retriever)
    retriever.retrieve.return_value = results or []
    return retriever


def make_mock_request(messages=None, system_prompt="You are helpful."):
    """创建模拟的 ModelRequest。"""
    request = MagicMock()
    request.messages = messages or [HumanMessage(content="hello")]
    request.system_prompt = system_prompt
    request.system_message = None

    def mock_override(**kwargs):
        new_req = MagicMock()
        new_req.messages = request.messages
        new_req.system_prompt = kwargs.get("system_prompt", request.system_prompt)
        return new_req

    request.override = MagicMock(side_effect=mock_override)
    return request


# ============================================================
# RetrievalResult 测试
# ============================================================

class TestRetrievalResult:
    """测试 RetrievalResult 数据类。"""

    def test_create_with_defaults(self):
        """默认值应正确。"""
        r = RetrievalResult(content="test content")
        assert r.content == "test content"
        assert r.source == ""
        assert r.score == 0.0

    def test_create_with_all_fields(self):
        """所有字段应可设置。"""
        r = RetrievalResult(content="content", source="doc.pdf", score=0.95)
        assert r.content == "content"
        assert r.source == "doc.pdf"
        assert r.score == 0.95

    def test_frozen(self):
        """应为不可变对象。"""
        r = RetrievalResult(content="test")
        with pytest.raises(AttributeError):
            r.content = "changed"


# ============================================================
# Retriever Protocol 测试
# ============================================================

class TestRetrieverProtocol:
    """测试 Retriever 协议的运行时检查。"""

    def test_compatible_class(self):
        """实现 retrieve 方法的类应符合协议。"""
        class MyRetriever:
            def retrieve(self, query: str, top_k: int = 5):
                return []

        assert isinstance(MyRetriever(), Retriever)

    def test_incompatible_class(self):
        """缺少 retrieve 方法的类不应符合协议。"""
        class NotRetriever:
            pass

        assert not isinstance(NotRetriever(), Retriever)


# ============================================================
# _format_results 测试
# ============================================================

class TestFormatResults:
    """测试结果格式化函数。"""

    def test_format_with_source(self):
        """带来源的结果应包含来源名。"""
        results = [RetrievalResult(content="content here", source="doc.pdf", score=0.9)]
        formatted = _format_results(results)
        assert "doc.pdf" in formatted
        assert "content here" in formatted

    def test_format_without_source(self):
        """无来源的结果不应报错。"""
        results = [RetrievalResult(content="content")]
        formatted = _format_results(results)
        assert "content" in formatted

    def test_format_multiple_results(self):
        """多条结果应带编号。"""
        results = [
            RetrievalResult(content="first", source="a.txt"),
            RetrievalResult(content="second", source="b.txt"),
        ]
        formatted = _format_results(results)
        assert "[1]" in formatted
        assert "[2]" in formatted

    def test_format_empty(self):
        """空列表应返回空字符串（虽然正常不会调用）。"""
        # _format_results 不处理空列表，但 KnowledgeMiddleware 会提前返回
        # 这里测试函数本身的行为
        formatted = _format_results([])
        assert isinstance(formatted, str)


# ============================================================
# KnowledgeMiddleware 测试
# ============================================================

class TestKnowledgeMiddleware:
    """测试 KnowledgeMiddleware。"""

    def test_passes_through_when_no_retriever_results(self):
        """检索无结果时应直接调用 handler。"""
        retriever = make_mock_retriever(results=[])
        middleware = KnowledgeMiddleware(retriever, top_k=3)

        request = make_mock_request(
            messages=[HumanMessage(content="query")]
        )
        handler = MagicMock(return_value="response")

        result = middleware.wrap_model_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "response"

    def test_injects_retrieved_context(self):
        """检索有结果时应注入系统提示词。"""
        results = [
            RetrievalResult(content="Python logging best practices", source="guide.pdf", score=0.9),
        ]
        retriever = make_mock_retriever(results=results)
        middleware = KnowledgeMiddleware(retriever, top_k=3)

        request = make_mock_request(
            messages=[HumanMessage(content="Python logging")],
            system_prompt="You are helpful.",
        )
        handler = MagicMock(return_value="response")

        middleware.wrap_model_call(request, handler)

        # retriever.retrieve 应被调用
        retriever.retrieve.assert_called_once_with("Python logging", top_k=3)

        # request.override 应被调用以注入知识
        request.override.assert_called_once()
        call_kwargs = request.override.call_args[1]
        assert "Knowledge Base" in call_kwargs["system_prompt"]
        assert "Python logging best practices" in call_kwargs["system_prompt"]

    def test_skips_non_human_messages(self):
        """非用户消息不应触发检索。"""
        retriever = make_mock_retriever(results=[
            RetrievalResult(content="some content"),
        ])
        middleware = KnowledgeMiddleware(retriever, top_k=3)

        request = make_mock_request(
            messages=[AIMessage(content="I am AI")]
        )
        handler = MagicMock(return_value="response")

        middleware.wrap_model_call(request, handler)

        retriever.retrieve.assert_not_called()
        handler.assert_called_once_with(request)

    def test_handles_retriever_exception(self):
        """检索器抛异常时不应阻断模型调用。"""
        retriever = MagicMock(spec=Retriever)
        retriever.retrieve.side_effect = RuntimeError("DB connection failed")

        middleware = KnowledgeMiddleware(retriever, top_k=3)
        request = make_mock_request(
            messages=[HumanMessage(content="query")]
        )
        handler = MagicMock(return_value="response")

        result = middleware.wrap_model_call(request, handler)

        # 应降级到直接调用 handler
        handler.assert_called_once_with(request)
        assert result == "response"

    def test_custom_top_k(self):
        """top_k 参数应传递给 retriever。"""
        retriever = make_mock_retriever(results=[])
        middleware = KnowledgeMiddleware(retriever, top_k=10)

        request = make_mock_request(
            messages=[HumanMessage(content="query")]
        )
        handler = MagicMock(return_value="response")

        middleware.wrap_model_call(request, handler)

        retriever.retrieve.assert_called_once_with("query", top_k=10)

    def test_preserves_original_system_prompt(self):
        """注入知识时应保留原始系统提示词。"""
        results = [RetrievalResult(content="knowledge", source="doc.txt")]
        retriever = make_mock_retriever(results=results)
        middleware = KnowledgeMiddleware(retriever, top_k=3)

        request = make_mock_request(
            messages=[HumanMessage(content="query")],
            system_prompt="Original prompt.",
        )
        handler = MagicMock(return_value="response")

        middleware.wrap_model_call(request, handler)

        call_kwargs = request.override.call_args[1]
        assert call_kwargs["system_prompt"].startswith("Original prompt.")
        assert "Knowledge Base" in call_kwargs["system_prompt"]
