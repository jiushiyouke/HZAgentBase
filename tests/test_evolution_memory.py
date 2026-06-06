"""测试进化记忆中间件 EvolutionMemoryMiddleware。"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from langchain_core.messages import HumanMessage, AIMessage

from hz_agent_base.middleware.evolution_memory import EvolutionMemoryMiddleware
from hz_agent_base.evolution_memory import (
    TaskExperience,
    TaskResult,
    classify_task,
    ExperienceStore,
    TaskEvaluator,
    TASK_PATTERNS,
    ReflectionCriteria,
    ReflectionEvaluator,
    ReflectionResult,
)


# ============================================================
# 辅助函数
# ============================================================

def make_mock_request(messages=None, system_prompt="You are helpful."):
    """创建一个模拟的 ModelRequest 对象。"""
    request = MagicMock()
    request.messages = messages or [HumanMessage(content="hello")]
    request.system_prompt = system_prompt

    def mock_override(**kwargs):
        new_req = MagicMock()
        new_req.messages = kwargs.get("messages", request.messages)
        new_req.system_prompt = kwargs.get("system_prompt", request.system_prompt)
        return new_req

    request.override = MagicMock(side_effect=mock_override)
    return request


def make_mock_response(content: str, tool_calls=None):
    """创建一个模拟的响应。"""
    msg = AIMessage(content=content)
    if tool_calls:
        msg.tool_calls = tool_calls
    return {"messages": [msg]}


def make_mock_model(response_content: str):
    """创建一个模拟的 LLM 模型。"""
    model = MagicMock()
    response = MagicMock()
    response.content = response_content
    model.invoke.return_value = response
    return model


# ============================================================
# 类型测试
# ============================================================

class TestClassifyTask:
    """测试任务分类（支持双关键字组合匹配）。"""

    def test_code_analysis_single(self):
        """单关键字匹配。"""
        assert classify_task("review this code") == "code_analysis"

    def test_code_analysis_double(self):
        """双关键字匹配：分析 + 代码。"""
        assert classify_task("分析这个项目的代码结构") == "code_analysis"

    def test_code_writing_single(self):
        """单关键字匹配。"""
        assert classify_task("implement a feature") == "code_writing"

    def test_code_writing_double(self):
        """双关键字匹配：写 + Python。"""
        assert classify_task("写一个 Python 脚本") == "code_writing"
        assert classify_task("Python 写脚本") == "code_writing"

    def test_research(self):
        assert classify_task("研究一下 React 和 Vue 的区别") == "research"

    def test_explanation(self):
        assert classify_task("解释一下什么是装饰器") == "explanation"

    def test_data_analysis_double(self):
        """双关键字匹配：分析 + 数据。"""
        assert classify_task("分析这些数据的趋势") == "data_analysis"

    def test_general(self):
        assert classify_task("你好") == "general"


class TestTaskExperience:
    """测试任务经验类型。"""

    def test_create_experience(self):
        exp = TaskExperience(
            id="exp_001",
            task="分析代码",
            task_type="code_analysis",
            strategy="先 glob 再 grep",
            tools_used=["glob", "grep"],
            result="success",
        )
        assert exp.id == "exp_001"
        assert exp.result == "success"


# ============================================================
# ExperienceStore 测试
# ============================================================

class TestExperienceStore:
    """测试经验存储。"""

    def test_save_and_get(self, tmp_path):
        """保存和获取。"""
        store = ExperienceStore(store_path=str(tmp_path / "evolution"))
        exp = TaskExperience(
            id="exp_001",
            task="分析代码",
            task_type="code_analysis",
            strategy="先 glob 再 grep",
            result="success",
        )
        store.save_experience(exp)

        experiences = store.get_experiences()
        assert len(experiences) == 1
        assert experiences[0].task == "分析代码"

    def test_get_by_type(self, tmp_path):
        """按类型获取。"""
        store = ExperienceStore(store_path=str(tmp_path / "evolution"))
        store.save_experience(TaskExperience(
            id="exp_001", task="分析代码", task_type="code_analysis",
            strategy="策略1", result="success",
        ))
        store.save_experience(TaskExperience(
            id="exp_002", task="写代码", task_type="code_writing",
            strategy="策略2", result="success",
        ))

        analysis = store.get_experiences(task_type="code_analysis")
        assert len(analysis) == 1
        assert analysis[0].task_type == "code_analysis"

    def test_get_similar(self, tmp_path):
        """获取类似经验。"""
        store = ExperienceStore(store_path=str(tmp_path / "evolution"))
        store.save_experience(TaskExperience(
            id="exp_001", task="Python 代码分析", task_type="code_analysis",
            strategy="先 glob 再 grep", result="success",
        ))
        store.save_experience(TaskExperience(
            id="exp_002", task="Java 代码分析", task_type="code_analysis",
            strategy="先 find 再 grep", result="success",
        ))

        similar = store.get_similar_experiences("Python 代码审查")
        assert len(similar) > 0

    def test_get_successful_strategies(self, tmp_path):
        """获取成功策略。"""
        store = ExperienceStore(store_path=str(tmp_path / "evolution"))
        store.save_experience(TaskExperience(
            id="exp_001", task="任务1", task_type="code_analysis",
            strategy="策略A", result="success",
        ))
        store.save_experience(TaskExperience(
            id="exp_002", task="任务2", task_type="code_analysis",
            strategy="策略B", result="failure",
        ))

        strategies = store.get_successful_strategies("code_analysis")
        assert len(strategies) == 1
        assert strategies[0] == "策略A"

    def test_format_for_prompt(self, tmp_path):
        """格式化用于提示词。"""
        store = ExperienceStore(store_path=str(tmp_path / "evolution"))
        experiences = [
            TaskExperience(
                id="exp_001", task="分析代码", task_type="code_analysis",
                strategy="先 glob 再 grep", tools_used=["glob", "grep"],
                result="success", lessons=["先看入口文件"],
            )
        ]

        formatted = store.format_experiences_for_prompt(experiences)
        assert "code_analysis" in formatted
        assert "先 glob 再 grep" in formatted


# ============================================================
# TaskEvaluator 测试
# ============================================================

class TestTaskEvaluator:
    """测试任务评估器。"""

    def test_evaluate_success(self):
        """评估成功任务。"""
        evaluator = TaskEvaluator()
        response = make_mock_response("任务完成")

        result = evaluator.evaluate(
            task="分析代码",
            messages=[HumanMessage(content="分析代码")],
            response=response,
        )
        assert result.success == True

    def test_evaluate_with_tools(self):
        """评估使用工具的任务。"""
        evaluator = TaskEvaluator()
        tool_call = {"name": "glob", "args": {"pattern": "*.py"}}
        response = make_mock_response("找到文件", tool_calls=[tool_call])

        result = evaluator.evaluate(
            task="分析代码",
            messages=[HumanMessage(content="分析代码")],
            response=response,
        )
        assert "glob" in result.tools_used

    def test_evaluate_error(self):
        """评估失败任务。"""
        evaluator = TaskEvaluator()
        response = make_mock_response("Error: 文件不存在")

        result = evaluator.evaluate(
            task="读取文件",
            messages=[HumanMessage(content="读取文件")],
            response=response,
        )
        assert result.success == False


# ============================================================
# AgentEvolutionMiddleware 测试
# ============================================================

class TestEvolutionMemoryMiddleware:
    """测试 Agent 进化中间件。"""

    def test_no_task(self):
        """无任务时直接通过。"""
        mw = EvolutionMemoryMiddleware(
            auto_classify=False,
            auto_evaluate=False,
            inject_experience=False,
        )
        request = make_mock_request()
        response = make_mock_response("Hello")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        assert result["messages"][0].content == "Hello"

    def test_inject_experience(self, tmp_path):
        """注入历史经验。"""
        # 预先存储一些经验
        store = ExperienceStore(store_path=str(tmp_path / "evolution"))
        store.save_experience(TaskExperience(
            id="exp_001", task="分析 Python 代码", task_type="code_analysis",
            strategy="先 glob 再 grep", result="success",
        ))

        mw = EvolutionMemoryMiddleware(
            memory_path=str(tmp_path / "evolution"),
            auto_classify=True,
            auto_evaluate=False,
            inject_experience=True,
        )
        request = make_mock_request([HumanMessage(content="分析 Python 代码结构")])
        response = make_mock_response("分析完成")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        # 检查系统提示词是否被修改
        call_args = handler.call_args[0][0]
        assert "glob" in call_args.system_prompt or "grep" in call_args.system_prompt

    def test_auto_evaluate(self, tmp_path):
        """自动评估。"""
        mw = EvolutionMemoryMiddleware(
            memory_path=str(tmp_path / "evolution"),
            auto_classify=True,
            auto_evaluate=True,
            inject_experience=False,
        )
        request = make_mock_request([HumanMessage(content="分析代码")])
        response = make_mock_response("分析完成")
        handler = MagicMock(return_value=response)

        mw.wrap_model_call(request, handler)

        # 检查经验是否被保存
        experiences = mw.store.get_experiences()
        assert len(experiences) == 1
        assert experiences[0].task_type == "code_analysis"


# ============================================================
# 集成测试
# ============================================================

class TestIntegration:
    """集成测试。"""

    def test_create_agent_with_evolution(self):
        """测试 create_agent 集成。"""
        from hz_agent_base import create_agent

        agent = create_agent(
            model="deepseek-v4-flash",
            middleware=[
                EvolutionMemoryMiddleware(
                    auto_classify=True,
                    auto_evaluate=True,
                )
            ],
        )
        assert agent is not None

    def test_priority_constant_exists(self):
        """测试优先级常量存在。"""
        from hz_agent_base.utils.constants import AGENT_MEMORY
        assert AGENT_MEMORY == 22

    def test_middleware_exported(self):
        """测试中间件被正确导出。"""
        from hz_agent_base.middleware import EvolutionMemoryMiddleware
        assert EvolutionMemoryMiddleware is not None

    def test_types_exported(self):
        """测试类型被正确导出。"""
        from hz_agent_base.evolution_memory import (
            TaskExperience,
            TaskResult,
            ExperienceStore,
            TaskEvaluator,
            ReflectionCriteria,
            ReflectionEvaluator,
            ReflectionResult,
        )
        assert TaskExperience is not None
        assert TaskResult is not None
        assert ExperienceStore is not None
        assert TaskEvaluator is not None
        assert ReflectionCriteria is not None
        assert ReflectionEvaluator is not None
        assert ReflectionResult is not None


# ============================================================
# ReflectionCriteria 测试
# ============================================================

class TestReflectionCriteria:
    """测试反思评估标准。"""

    def test_default_dimensions(self):
        """默认维度。"""
        criteria = ReflectionCriteria()
        assert "completeness" in criteria.dimensions
        assert "accuracy" in criteria.dimensions

    def test_task_type_code(self):
        """代码任务类型。"""
        criteria = ReflectionCriteria(task_type="code")
        assert "correctness" in criteria.dimensions
        assert "efficiency" in criteria.dimensions

    def test_custom_dimensions(self):
        """自定义维度。"""
        criteria = ReflectionCriteria(dimensions=["custom1", "custom2"])
        assert criteria.dimensions == ["custom1", "custom2"]

    def test_threshold(self):
        """质量阈值。"""
        criteria = ReflectionCriteria(threshold=0.8)
        assert criteria.threshold == 0.8


# ============================================================
# ReflectionEvaluator 测试
# ============================================================

class TestReflectionEvaluator:
    """测试反思评估器。"""

    def test_evaluate_success(self):
        """评估成功。"""
        model = make_mock_model(json.dumps({
            "dimensions": {"completeness": 0.8, "accuracy": 0.9},
            "overall": 0.85,
            "issues": ["回答太短"],
            "suggestions": ["增加示例"],
        }))
        criteria = ReflectionCriteria(dimensions=["completeness", "accuracy"])
        evaluator = ReflectionEvaluator(criteria=criteria, model=model)

        result = evaluator.evaluate("问题", "回答")
        assert result.overall == 0.85
        assert result.passed == True

    def test_evaluate_below_threshold(self):
        """评估不达标。"""
        model = make_mock_model(json.dumps({
            "dimensions": {"completeness": 0.5, "accuracy": 0.6},
            "overall": 0.55,
            "issues": ["回答太短"],
            "suggestions": ["增加示例"],
        }))
        criteria = ReflectionCriteria(dimensions=["completeness", "accuracy"], threshold=0.7)
        evaluator = ReflectionEvaluator(criteria=criteria, model=model)

        result = evaluator.evaluate("问题", "回答")
        assert result.overall == 0.55
        assert result.passed == False

    def test_evaluate_no_model(self):
        """无模型时返回默认结果。"""
        criteria = ReflectionCriteria(dimensions=["completeness"])
        evaluator = ReflectionEvaluator(criteria=criteria, model=None)

        result = evaluator.evaluate("问题", "回答")
        assert result.passed == True


# ============================================================
# EvolutionMemoryMiddleware 重试测试
# ============================================================

class TestEvolutionMemoryMiddlewareRetry:
    """测试进化记忆中间件的重试功能。"""

    def test_quality_pass_no_retry(self):
        """质量达标，不重试。"""
        model = make_mock_model(json.dumps({
            "dimensions": {"completeness": 0.8},
            "overall": 0.8,
            "issues": [],
            "suggestions": [],
        }))
        mw = EvolutionMemoryMiddleware(
            model=model,
            quality_threshold=0.7,
            max_attempts=3,
            auto_evaluate=False,
            inject_experience=False,
        )
        request = make_mock_request()
        response = make_mock_response("Good answer")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        assert result["messages"][0].content == "Good answer"
        assert handler.call_count == 1

    def test_quality_fail_retry(self):
        """质量不达标，重试。"""
        model = MagicMock()
        model.invoke.side_effect = [
            MagicMock(content=json.dumps({
                "dimensions": {"completeness": 0.5},
                "overall": 0.5,
                "issues": ["太短"],
                "suggestions": ["详细点"],
            })),
            MagicMock(content=json.dumps({
                "dimensions": {"completeness": 0.8},
                "overall": 0.8,
                "issues": [],
                "suggestions": [],
            })),
        ]
        mw = EvolutionMemoryMiddleware(
            model=model,
            quality_threshold=0.7,
            max_attempts=3,
            auto_evaluate=False,
            inject_experience=False,
        )
        request = make_mock_request()
        response = make_mock_response("Better answer")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        assert handler.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
