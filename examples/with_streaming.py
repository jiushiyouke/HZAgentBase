"""示例：流式输出（逐 token 返回）。

使用 run_agent_stream() 同步流式输出，
或 arun_agent_stream() 异步流式输出（适用于 FastAPI + SSE）。

用法:
    python examples/with_streaming.py
"""

from hz_agent_base import create_agent, run_agent_stream

# 创建 agent
agent = create_agent()

# 同步流式输出
print("=== 同步流式输出 ===")
for token in run_agent_stream(agent, "用一句话介绍 Python"):
    print(token, end="", flush=True)
print("\n")


# 异步流式输出示例（适用于 FastAPI + SSE）
"""
import asyncio
from hz_agent_base import arun_agent_stream

async def main():
    async for token in arun_agent_stream(agent, "用一句话介绍 Python"):
        print(token, end="", flush=True)
    print()

asyncio.run(main())
"""


# FastAPI + SSE 集成示例
"""
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

@app.post("/chat")
async def chat(message: str):
    async def generate():
        async for token in arun_agent_stream(agent, message):
            yield f"data: {token}\\n\\n"
        yield "data: [DONE]\\n\\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
"""
