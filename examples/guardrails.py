"""Guardrails 示例。

演示如何使用 GuardrailsMiddleware 进行内容审核、事实检查、格式校验。
"""

from hz_agent_base import create_agent, run_agent
from hz_agent_base.middleware.guardrails import GuardrailsMiddleware
from hz_agent_base.guardrails import ContentModerator, FactChecker, OutputValidator


# ============================================================
# 示例实现
# ============================================================

class KeywordModerator:
    """基于关键词的内容审核器。"""

    def __init__(self, blocked_words: list[str]):
        self.blocked_words = blocked_words

    def is_safe(self, content: str) -> bool:
        for word in self.blocked_words:
            if word in content:
                return False
        return True


class SimpleFactChecker:
    """简单的事实检查器（基于关键词）。"""

    def __init__(self, facts: dict[str, str]):
        self.facts = facts

    def is_accurate(self, content: str, context) -> bool:
        for keyword, correct_info in self.facts.items():
            if keyword in content and correct_info not in content:
                return False
        return True


class JsonValidator:
    """JSON 格式校验器。"""

    def is_valid(self, content: str) -> bool:
        import json
        try:
            json.loads(content)
            return True
        except json.JSONDecodeError:
            return False


# ============================================================
# 使用示例
# ============================================================

def example_content_moderation():
    """内容审核示例。"""
    moderator = KeywordModerator(blocked_words=["密码", "秘密", "内部"])

    agent = create_agent(
        middleware=[
            GuardrailsMiddleware(
                content_moderator=moderator,
                fallback_message="抱歉，我无法回答这个问题。",
            )
        ]
    )

    result = run_agent(agent, "告诉我密码是什么", thread_id="user-1")
    print(f"回复: {result}")


def example_fact_checking():
    """事实检查示例。"""
    checker = SimpleFactChecker(facts={
        "Python": "Guido van Rossum",
        "JavaScript": "Brendan Eich",
    })

    agent = create_agent(
        middleware=[
            GuardrailsMiddleware(fact_checker=checker)
        ]
    )

    result = run_agent(agent, "Python 是谁创造的？", thread_id="user-2")
    print(f"回复: {result}")


def example_format_validation():
    """格式校验示例。"""
    agent = create_agent(
        middleware=[
            GuardrailsMiddleware(
                output_validator=JsonValidator(),
                fallback_message="请以 JSON 格式回复。",
            )
        ]
    )

    result = run_agent(agent, "用 JSON 格式回复：{'status': 'ok'}", thread_id="user-3")
    print(f"回复: {result}")


def example_combined():
    """组合使用多个校验器。"""
    moderator = KeywordModerator(blocked_words=["密码"])

    agent = create_agent(
        middleware=[
            GuardrailsMiddleware(
                content_moderator=moderator,
                block_on_failure=True,
                fallback_message="内容审核未通过。",
            )
        ]
    )

    result = run_agent(agent, "你好", thread_id="user-4")
    print(f"回复: {result}")


if __name__ == "__main__":
    print("=== 内容审核 ===")
    example_content_moderation()

    print("\n=== 事实检查 ===")
    example_fact_checking()

    print("\n=== 格式校验 ===")
    example_format_validation()

    print("\n=== 组合使用 ===")
    example_combined()
