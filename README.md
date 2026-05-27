# HZAgentBase

Reusable Agent Harness infrastructure library.

## Installation

```bash
pip install hz-agent-base
```

## Quick Start

```python
from hz_agent_base import create_agent

# Default model: deepseek-v4-flash
agent = create_agent()
result = agent.invoke({"messages": [{"role": "user", "content": "Hello!"}]})
```

## Features

- **Permission System**: Fine-grained control over tool execution
- **Hook System**: Lifecycle events for tool calls
- **Memory System**: Persistent cross-session knowledge
- **Multi-Agent**: Coordinator/worker orchestration
- **Pluggable Backends**: Local, sandbox, or remote execution

## Configuration

Set your DeepSeek API key:

```bash
export DEEPSEEK_API_KEY="your-api-key"
```
