"""进化记忆示例。

演示如何使用 EvolutionMemoryMiddleware 实现 Agent 从任务中学习、持续进化。
"""

from hz_agent_base import create_agent, run_agent
from hz_agent_base.middleware.evolution_memory import EvolutionMemoryMiddleware


def example_basic():
    """基础用法：自动进化。"""
    agent = create_agent(
        middleware=[
            EvolutionMemoryMiddleware(
                memory_path=".evolution_memory/",
                auto_classify=True,
                auto_evaluate=True,
                inject_experience=True,
            )
        ]
    )

    # 第一次：没有历史经验
    result = run_agent(agent, "分析这个项目的代码结构", thread_id="user-1")
    print(f"第一次回复: {result}")

    # 第二次：会注入历史经验
    result = run_agent(agent, "分析另一个项目的代码结构", thread_id="user-1")
    print(f"第二次回复: {result}")


def example_with_model():
    """带模型的进化（自动提取教训）。"""
    from hz_agent_base.config import _get_model

    model = _get_model()

    agent = create_agent(
        middleware=[
            EvolutionMemoryMiddleware(
                memory_path=".evolution_memory/",
                auto_classify=True,
                auto_evaluate=True,
                inject_experience=True,
                model=model,  # 用于提取教训
            )
        ]
    )

    result = run_agent(agent, "写一个 Python 脚本分析日志", thread_id="user-2")
    print(f"回复: {result}")


def example_custom():
    """自定义配置。"""
    agent = create_agent(
        middleware=[
            EvolutionMemoryMiddleware(
                memory_path=".evolution_memory/",
                retrieval_top_k=3,      # 最多注入 3 条经验
                auto_classify=True,      # 自动分类任务
                auto_evaluate=True,      # 自动评估结果
                inject_experience=True,  # 注入历史经验
            )
        ]
    )

    # 不同类型的任务
    tasks = [
        "分析代码结构",
        "写一个排序算法",
        "解释 Python 装饰器",
        "研究 React 和 Vue 的区别",
    ]

    for task in tasks:
        result = run_agent(agent, task, thread_id="user-3")
        print(f"任务: {task}")
        print(f"回复: {result[:100]}...")
        print()


def example_read_evolution():
    """读取进化记录。"""
    from hz_agent_base.agent_evolution import ExperienceStore

    store = ExperienceStore(store_path=".agent_evolution/")

    # 获取所有经验
    all_experiences = store.get_experiences()
    print(f"总经验数: {len(all_experiences)}")

    # 按类型获取
    for task_type in ["code_analysis", "code_writing", "research"]:
        experiences = store.get_experiences(task_type=task_type)
        print(f"{task_type}: {len(experiences)} 条经验")

    # 获取成功策略
    strategies = store.get_successful_strategies("code_analysis")
    print(f"\n代码分析成功策略:")
    for s in strategies:
        print(f"  - {s}")

    # 获取常见教训
    lessons = store.get_common_lessons()
    print(f"\n常见教训:")
    for l in lessons:
        print(f"  - {l}")


if __name__ == "__main__":
    print("=== 基础用法 ===")
    example_basic()

    print("\n=== 带模型 ===")
    example_with_model()

    print("\n=== 自定义配置 ===")
    example_custom()

    print("\n=== 读取进化记录 ===")
    example_read_evolution()
