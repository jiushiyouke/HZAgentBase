"""中间件优先级常量。

用于 create_agent(middleware=[...]) 中控制自定义中间件的执行位置。

用法：
    from hz_agent_base.middleware.constants import BEFORE_ALL, AFTER_ALL

    agent = create_agent(
        model="deepseek-v4-flash",
        middleware=[
            (RequestLogger(), BEFORE_ALL),     # 最前面
            (BusinessContext()),                # 默认位置（DEFAULT=30）
            (OutputSanitizer(), AFTER_ALL),    # 最后面
        ],
    )
"""

# 数字越小越先执行
BEFORE_ALL = 0
PERMISSION = 5
HOOKS = 10
MEMORY = 20
KNOWLEDGE = 25
DEFAULT = 30      # 用户自定义中间件的默认位置
AUDIT = 35
RESILIENT = 40
COORDINATOR = 50
AFTER_ALL = 100
