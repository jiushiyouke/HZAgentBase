"""示例：在服务器项目中集成 HZAgentBase。

HZAgentBase 作为组件库使用，不关心 HTTP 框架和用户管理。
你的服务器工程负责交互层，HZAgentBase 只负责创建和运行 Agent。

运行方式（需要安装 fastapi 和 uvicorn）：
    pip install fastapi uvicorn
    uvicorn examples.server_integration:app --reload
"""

from fastapi import FastAPI
from pydantic import BaseModel

from hz_agent_base import create_agent, run_agent, arun_agent_stream, WorkerConfig, PermissionSettings

# ============================================================
# 1. 启动时创建 Agent（全局单例，线程安全）
# ============================================================

agent = create_agent(
    model="deepseek-v4-flash",
    permissions=PermissionSettings(mode="DEFAULT"),
    memory_path=".server_memory/",
    filesystem={"log_path": "audit.jsonl"},
    workers=[
        WorkerConfig(name="researcher", prompt="研究助手，负责搜索和分析"),
        WorkerConfig(name="coder", prompt="编程助手，负责写代码"),
    ],
)

# ============================================================
# 2. FastAPI 应用（你的工程负责这部分）
# ============================================================

app = FastAPI(title="Agent Service")


class ChatRequest(BaseModel):
    user_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """处理用户消息。

    注意：run_agent() 是同步阻塞调用，这里用普通 def 而非 async def，
    FastAPI 会自动将其放入线程池执行，不会阻塞事件循环。

    user_id 作为 thread_id，天然实现多用户隔离。
    不同用户的对话互不干扰。
    """
    result = run_agent(agent, req.message, thread_id=req.user_id)

    # 提取最后一条 AI 回复
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "type") and msg.type == "ai":
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            return ChatResponse(reply=content)

    return ChatResponse(reply="No response")


# ============================================================
# 3. 流式输出端点（SSE）
# ============================================================

from fastapi.responses import StreamingResponse


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """流式输出端点 — 逐 token 返回，适用于前端实时显示。

    使用 Server-Sent Events (SSE) 协议：
    - 每个 token 以 `data: {token}` 格式发送
    - 完成时发送 `data: [DONE]`

    前端接收示例（JavaScript）：
        const es = new EventSource('/chat/stream', {
            method: 'POST',
            body: JSON.stringify({user_id: 'user-1', message: '你好'})
        });
        es.onmessage = (e) => {
            if (e.data === '[DONE]') es.close();
            else appendToUI(e.data);
        };
    """
    async def generate():
        async for token in arun_agent_stream(agent, req.message, thread_id=req.user_id):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
