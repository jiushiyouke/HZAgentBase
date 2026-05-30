"""示例：异步调用 Agent。

使用 arun_agent() 异步运行 Agent，适用于 FastAPI 等异步框架。

用法:
    pip install fastapi uvicorn
    uvicorn examples.async_agent:app --reload
"""

import asyncio
from hz_agent_base import create_agent, arun_agent

# 创建 agent（全局单例，线程安全）
agent = create_agent()


# 基本异步调用
async def main():
    result = await arun_agent(agent, "你好", thread_id="demo")
    for msg in result.get("messages", []):
        if hasattr(msg, "type") and msg.type == "ai":
            print(f"Agent: {msg.content}")


# FastAPI 集成示例
"""
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class ChatRequest(BaseModel):
    user_id: str
    message: str

@app.post("/chat")
async def chat(req: ChatRequest):
    result = await arun_agent(agent, req.message, thread_id=req.user_id)
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "type") and msg.type == "ai":
            return {"reply": msg.content}
    return {"reply": "No response"}
"""

if __name__ == "__main__":
    asyncio.run(main())
