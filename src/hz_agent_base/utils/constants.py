"""中间件优先级常量。

用于 create_agent(middleware=[...]) 中控制自定义中间件的执行位置。

执行顺序（数字越小越先执行）：
    BEFORE_ALL(0)
    → PERMISSION(5)          # 权限检查
    → HUMAN_APPROVAL(8)      # Human-in-the-loop 人工审批
    → HOOKS(10)              # 生命周期事件
    → MEMORY(20)             # 记忆注入/提取
    → AGENT_MEMORY(22)       # 跨会话 Agent 记忆
    → KNOWLEDGE(25)          # 知识库 RAG 检索
    → CONVERSATION_HISTORY(28) # 对话历史管理
    → DEFAULT(30)            # 用户自定义（默认位置）
    → GUARDRAILS(32)         # Guardrails 内容审核
    → SANITIZER(33)          # 输出清洗 PII 过滤
    → REFLECTION(34)         # Agent 自我反思
    → AUDIT(35)              # 文件审计
    → RESILIENT(40)          # 重试/取消/终止
    → COORDINATOR(50)        # 多 Agent 编排
    → AFTER_ALL(100)

用法：
    from hz_agent_base.utils.constants import BEFORE_ALL, AFTER_ALL

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
HUMAN_APPROVAL = 8         # Human-in-the-loop：危险操作需人工确认
HOOKS = 10
MEMORY = 20
AGENT_MEMORY = 22          # 跨会话 Agent 记忆：Agent 积累经验
KNOWLEDGE = 25
CONVERSATION_HISTORY = 28  # 对话历史管理：防止 token 超限
DEFAULT = 30               # 用户自定义中间件的默认位置
GUARDRAILS = 32            # Guardrails：内容审核、幻觉检测、格式校验
SANITIZER = 33             # 输出清洗：PII 过滤、敏感词、prompt 泄露检测
REFLECTION = 34            # Agent 自我反思：评估输出质量，自动修正
AUDIT = 35
RESILIENT = 40
COORDINATOR = 50
AFTER_ALL = 100
