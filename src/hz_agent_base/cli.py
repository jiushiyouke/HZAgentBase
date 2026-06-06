"""CLI entry point for HZAgentBase.

命令结构：
    hz-agent help                    # 使用示例和快速指引
    hz-agent config show|check|path  # 配置管理
    hz-agent chat [--stream]         # 交互式对话
    hz-agent run [--stream]          # 单次执行
    hz-agent memory list|show|search|clear  # 记忆管理
    hz-agent audit show|stats|export|verify # 审计日志
    hz-agent version                 # 版本信息
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from .agent import create_agent, run_agent, run_agent_stream
from .permissions import PermissionSettings, PermissionMode


console = Console()


# ============================================================
# 主命令组
# ============================================================

@click.group()
@click.version_option()
def main():
    """HZAgentBase - Agent Harness CLI."""
    pass


# ============================================================
# help — 使用示例和快速指引
# ============================================================

@main.command()
def help():
    """显示使用示例和快速指引。"""
    text = """\
# HZAgentBase CLI

## 快速开始

```bash
# 1. 配置
cp .env-example .env        # 编辑 .env，填入 MODEL_API_KEY

# 2. 检查环境
hz-agent config check

# 3. 开始对话
hz-agent chat
hz-agent chat --stream       # 流式输出
```

## 常用命令

| 命令 | 说明 |
|------|------|
| `hz-agent chat` | 交互式对话 |
| `hz-agent chat --stream` | 流式输出（逐字显示） |
| `hz-agent chat --sanitizer` | 启用 PII 脱敏 |
| `hz-agent chat --guardrails` | 启用内容护栏 |
| `hz-agent chat --evolution-memory` | 启用进化记忆 |
| `hz-agent run "问题"` | 单次执行 |
| `hz-agent run "问题" --stream` | 单次执行 + 流式输出 |
| `hz-agent run "问题" --output json` | 单次执行，JSON 输出 |
| `hz-agent config show` | 查看所有配置 |
| `hz-agent config check` | 检查环境和 API 连通性 |
| `hz-agent config path` | 显示 .env 文件路径 |
| `hz-agent memory list` | 列出所有记忆 |
| `hz-agent memory show <name>` | 查看记忆内容 |
| `hz-agent memory search <query>` | 搜索相关记忆 |
| `hz-agent memory clear` | 清空所有记忆 |
| `hz-agent evolution list` | 查看进化经验 |
| `hz-agent evolution stats` | 进化记忆统计 |
| `hz-agent evolution show <id>` | 查看经验详情 |
| `hz-agent evolution similar <query>` | 搜索相似经验 |
| `hz-agent evolution clear` | 清空进化记忆 |
| `hz-agent audit show` | 查看审计日志 |
| `hz-agent audit stats` | 审计统计汇总 |
| `hz-agent audit export` | 导出审计日志（CSV） |
| `hz-agent audit verify` | 校验审计日志完整性 |
| `hz-agent version` | 版本和环境信息 |

## 支持的模型

| 前缀 | 提供商 | 需要安装 |
|------|--------|----------|
| `deepseek-*` | DeepSeek | 默认支持 |
| `gpt-*` / `o1-*` / `o3-*` | OpenAI | 默认支持 |
| `claude-*` | Anthropic | `pip install langchain-anthropic` |
| `gemini-*` | Google Gemini | `pip install langchain-google-genai` |
| 其他 | Ollama/vLLM 等 | 设置 MODEL_BASE_URL |

## 文档

https://github.com/jiushiyouke/HZAgentBase
"""
    console.print(Markdown(text))


# ============================================================
# config — 配置管理
# ============================================================

@main.group()
def config():
    """配置管理命令。"""
    pass


@config.command("show")
def config_show():
    """显示所有加载的配置。"""
    from .config import load_config

    cfg = load_config()

    table = Table(title="HZAgentBase 配置")
    table.add_column("配置项", style="bold")
    table.add_column("值")
    table.add_column("来源", style="dim")

    for key, value in cfg.items():
        # 隐藏 API Key 中间部分
        if key == "MODEL_API_KEY" and value:
            display_value = value[:6] + "****" + value[-4:] if len(value) > 10 else "****"
        else:
            display_value = value or "（未设置）"
        table.add_row(key, display_value)

    console.print(table)


@config.command("check")
def config_check():
    """检查环境配置和 API 连通性。"""
    from .config import load_config

    cfg = load_config()
    issues = []

    # 检查 .env 是否加载
    api_key = cfg.get("MODEL_API_KEY", "")
    if not api_key:
        issues.append("[red]FAIL[/] MODEL_API_KEY 未设置")
    else:
        console.print("[green]OK[/] MODEL_API_KEY 已设置")

    model = cfg.get("DEFAULT_MODEL", "")
    if not model:
        issues.append("[red]FAIL[/] DEFAULT_MODEL 未设置")
    else:
        console.print(f"[green]OK[/] DEFAULT_MODEL: {model}")

    base_url = cfg.get("MODEL_BASE_URL", "")
    if base_url:
        console.print(f"[green]OK[/] MODEL_BASE_URL: {base_url}")
        if base_url.startswith("http://"):
            issues.append("[yellow]WARN[/] MODEL_BASE_URL 使用 HTTP（非 HTTPS）")

    # 检查 Python 版本
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    console.print(f"[green]OK[/] Python: {py_version}")

    # 检查关键依赖
    try:
        import deepagents
        console.print(f"[green]OK[/] deepagents: {deepagents.__version__}")
    except ImportError:
        issues.append("[red]FAIL[/] deepagents 未安装")

    try:
        import langgraph
        console.print("[green]OK[/] langgraph 已安装")
    except ImportError:
        issues.append("[red]FAIL[/] langgraph 未安装")

    # 尝试创建 agent（不调用 API）
    if api_key:
        try:
            agent = create_agent(model=model)
            console.print("[green]OK[/] Agent 创建成功")
        except Exception as e:
            issues.append(f"[red]FAIL[/] Agent 创建失败: {e}")

    if issues:
        console.print("\n[bold yellow]发现以下问题：[/]")
        for issue in issues:
            console.print(f"  {issue}")
    else:
        console.print("\n[bold green]环境检查通过！[/]")


@config.command("path")
def config_path():
    """显示 .env 文件路径。"""
    from pathlib import Path as P

    current = P.cwd()
    found = False
    while current != current.parent:
        candidate = current / ".env"
        if candidate.exists():
            console.print(f"[green]OK[/] .env 路径: {candidate}")
            found = True
            break
        current = current.parent

    if not found:
        console.print("[yellow]未找到 .env 文件[/]")
        console.print("请复制 .env-example 为 .env 并填入配置")


# ============================================================
# chat — 交互式对话
# ============================================================

@main.command()
@click.option("--model", default=None, help="LLM model (default: deepseek-v4-flash)")
@click.option("--auto", is_flag=True, help="Full auto mode (no confirmations)")
@click.option("--plan", is_flag=True, help="Plan mode (read-only)")
@click.option("--memory", default=None, help="Path to memory directory")
@click.option("--rules", default=None, help="Path to shared rules directory")
@click.option("--prompt", default=None, help="System prompt (string or file/directory path)")
@click.option("--filesystem", is_flag=True, help="Enable file operation audit")
@click.option("--stream", is_flag=True, help="Enable streaming output")
@click.option("--sanitizer", is_flag=True, help="Enable PII masking and sensitive word filtering")
@click.option("--guardrails", is_flag=True, help="Enable content moderation and fact checking")
@click.option("--evolution-memory", is_flag=True, help="Enable evolution memory (learn from tasks)")
@click.option("--conversation-history", is_flag=True, help="Enable conversation history management")
@click.option("--api-key", default=None, help="API key override")
def chat(
    model: str | None,
    auto: bool,
    plan: bool,
    memory: str | None,
    rules: str | None,
    prompt: str | None,
    filesystem: bool,
    stream: bool,
    sanitizer: bool,
    guardrails: bool,
    evolution_memory: bool,
    conversation_history: bool,
    api_key: str | None,
):
    """交互式对话。"""
    mode = PermissionMode.FULL_AUTO if auto else (PermissionMode.PLAN if plan else PermissionMode.DEFAULT)

    agent = create_agent(
        model=model,
        system_prompt=prompt,
        rules=[rules] if rules else None,
        permissions=PermissionSettings(mode=mode),
        memory_path=memory,
        filesystem=filesystem,
        sanitizer=sanitizer,
        guardrails={} if guardrails else None,
        evolution_memory=evolution_memory,
        conversation_history=conversation_history,
        api_key=api_key,
    )

    # 显示启用的功能
    console.print("[bold green]HZAgentBase Chat[/bold green]")
    model_name = model or "deepseek-v4-flash"
    features = [f"Model: {model_name}", f"Mode: {mode.value}"]
    if stream:
        features.append("Stream: ON")
    if sanitizer:
        features.append("Sanitizer: ON")
    if guardrails:
        features.append("Guardrails: ON")
    if evolution_memory:
        features.append("Evolution: ON")
    if conversation_history:
        features.append("History: ON")
    console.print(" | ".join(features))
    if memory:
        console.print(f"Memory: {memory}")
    if rules:
        console.print(f"Rules: {rules}")
    console.print("Type 'exit' or 'quit' to end the session.\n")

    thread_id = "cli-session"

    while True:
        try:
            user_input = console.input("[bold cyan]You:[/] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\nGoodbye!")
            break

        if user_input.strip().lower() in ("exit", "quit"):
            console.print("Goodbye!")
            break

        if not user_input.strip():
            continue

        try:
            if stream:
                console.print(f"\n[bold blue]Agent:[/]", end=" ")
                for token in run_agent_stream(agent, user_input, thread_id=thread_id):
                    console.print(token, end="", highlight=False)
                console.print("\n")
            else:
                result = run_agent(agent, user_input, thread_id=thread_id)
                messages = result.get("messages", [])
                for msg in messages:
                    if hasattr(msg, "type") and msg.type == "ai":
                        content = msg.content if isinstance(msg.content, str) else str(msg.content)
                        console.print(f"\n[bold blue]Agent:[/]")
                        console.print(Markdown(content))
                        console.print()

        except Exception as e:
            console.print(f"[bold red]Error:[/] {e}")


# ============================================================
# run — 单次执行
# ============================================================

@main.command()
@click.argument("prompt")
@click.option("--model", default=None, help="LLM model")
@click.option("--auto", is_flag=True, help="Full auto mode")
@click.option("--thread", default=None, help="Thread ID for session isolation")
@click.option("--stream", is_flag=True, help="Enable streaming output")
@click.option("--output", "output_format", default=None, type=click.Choice(["json"]), help="Output format")
@click.option("--sanitizer", is_flag=True, help="Enable PII masking and sensitive word filtering")
@click.option("--guardrails", is_flag=True, help="Enable content moderation and fact checking")
@click.option("--evolution-memory", is_flag=True, help="Enable evolution memory")
@click.option("--conversation-history", is_flag=True, help="Enable conversation history management")
@click.option("--api-key", default=None, help="API key override")
def run(
    prompt: str,
    model: str | None,
    auto: bool,
    thread: str | None,
    stream: bool,
    output_format: str | None,
    sanitizer: bool,
    guardrails: bool,
    evolution_memory: bool,
    conversation_history: bool,
    api_key: str | None,
):
    """单次执行并输出结果。"""
    mode = PermissionMode.FULL_AUTO if auto else PermissionMode.DEFAULT

    agent = create_agent(
        model=model,
        permissions=PermissionSettings(mode=mode),
        sanitizer=sanitizer,
        guardrails={} if guardrails else None,
        evolution_memory=evolution_memory,
        conversation_history=conversation_history,
        api_key=api_key,
    )

    try:
        if stream:
            for token in run_agent_stream(agent, prompt, thread_id=thread):
                if output_format == "json":
                    # JSON 流式模式：每行一个 JSON
                    print(json.dumps({"type": "token", "content": token}, ensure_ascii=False))
                else:
                    console.print(token, end="", highlight=False)
            if not output_format:
                console.print()  # 换行
        else:
            result = run_agent(agent, prompt, thread_id=thread)
            messages = result.get("messages", [])

            if output_format == "json":
                # 提取最后一条 AI 回复
                reply = ""
                for msg in messages:
                    if hasattr(msg, "type") and msg.type == "ai":
                        reply = msg.content if isinstance(msg.content, str) else str(msg.content)
                print(json.dumps({"type": "result", "content": reply}, ensure_ascii=False))
            else:
                for msg in messages:
                    if hasattr(msg, "type") and msg.type == "ai":
                        console.print(msg.content)
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        sys.exit(1)


# ============================================================
# version — 版本信息
# ============================================================

@main.command()
def version():
    """显示版本和环境信息。"""
    from . import __version__

    table = Table(title="HZAgentBase")
    table.add_column("Key", style="bold")
    table.add_column("Value")
    table.add_row("Version", __version__)

    try:
        from .config import DEFAULT_MODEL, MODEL_BASE_URL
        table.add_row("Default Model", DEFAULT_MODEL)
        table.add_row("API Base URL", MODEL_BASE_URL or "（自动检测）")
    except Exception:
        table.add_row("Config", "Not loaded")

    console.print(table)


# ============================================================
# memory — 记忆管理
# ============================================================

@main.group()
def memory():
    """记忆管理命令。"""
    pass


@memory.command("list")
@click.option("--path", default=".memory", help="Memory directory path")
def memory_list(path: str):
    """列出所有存储的记忆。"""
    memory_path = Path(path)
    if not memory_path.exists():
        console.print(f"[yellow]记忆目录不存在:[/] {path}")
        return

    table = Table(title=f"记忆列表 ({path})")
    table.add_column("名称", style="bold")
    table.add_column("文件")
    table.add_column("类型", style="dim")
    table.add_column("描述")

    files = sorted(memory_path.glob("*.md"))
    count = 0
    for f in files:
        if f.name == "MEMORY.md":
            continue
        # 解析 frontmatter
        name = f.stem
        memory_type = ""
        description = ""
        try:
            content = f.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = parts[1]
                    for line in frontmatter.strip().split("\n"):
                        if line.startswith("type:"):
                            memory_type = line.split(":", 1)[1].strip()
                        elif line.startswith("description:"):
                            description = line.split(":", 1)[1].strip()
        except Exception:
            pass

        table.add_row(name, f.name, memory_type, description)
        count += 1

    if count == 0:
        console.print("[yellow]没有找到记忆。[/]")
    else:
        console.print(table)
        console.print(f"\n共 {count} 条记忆")


@memory.command("show")
@click.argument("name")
@click.option("--path", default=".memory", help="Memory directory path")
def memory_show(name: str, path: str):
    """查看指定记忆的内容。"""
    memory_path = Path(path)
    target = memory_path / f"{name}.md"

    if not target.exists():
        console.print(f"[red]记忆不存在:[/] {name}")
        console.print(f"使用 `hz-agent memory list` 查看所有记忆")
        return

    content = target.read_text(encoding="utf-8")
    console.print(Markdown(content))


@memory.command("search")
@click.argument("query")
@click.option("--path", default=".memory", help="Memory directory path")
@click.option("--limit", default=5, help="Max results")
def memory_search(query: str, path: str, limit: int):
    """搜索相关记忆。"""
    from .memory.relevance import select_relevant_memories

    memory_path = Path(path)
    if not memory_path.exists():
        console.print(f"[yellow]记忆目录不存在:[/] {path}")
        return

    results = select_relevant_memories(query, memory_path, max_results=limit)

    if not results:
        console.print(f"[yellow]未找到与 '{query}' 相关的记忆。[/]")
        return

    table = Table(title=f"搜索结果: '{query}'")
    table.add_column("名称", style="bold")
    table.add_column("分数", style="dim")
    table.add_column("内容")

    for r in results:
        content_preview = r.content[:100] + "..." if len(r.content) > 100 else r.content
        table.add_row(r.source, f"{r.score:.2f}", content_preview)

    console.print(table)


@memory.command("clear")
@click.option("--path", default=".memory", help="Memory directory path")
@click.option("--confirm", is_flag=True, help="Skip confirmation")
def memory_clear(path: str, confirm: bool):
    """清空所有记忆。"""
    memory_path = Path(path)
    if not memory_path.exists():
        console.print(f"[yellow]记忆目录不存在:[/] {path}")
        return

    files = [f for f in memory_path.glob("*.md") if f.name != "MEMORY.md"]
    if not files:
        console.print("[yellow]没有记忆需要清理。[/]")
        return

    if not confirm:
        console.print(f"[bold yellow]即将删除 {len(files)} 条记忆：[/]")
        for f in files:
            console.print(f"  - {f.stem}")
        if not click.confirm("确认删除？"):
            console.print("已取消。")
            return

    for f in files:
        f.unlink()

    console.print(f"[green]已删除 {len(files)} 条记忆。[/]")


# ============================================================
# audit — 审计日志
# ============================================================

@main.group()
def audit():
    """审计日志命令。"""
    pass


@audit.command("show")
@click.option("--path", default=".audit/audit.jsonl", help="Audit log file path")
@click.option("--limit", default=20, help="Number of recent entries to show")
@click.option("--tool", default=None, help="Filter by tool name")
@click.option("--file", "file_filter", default=None, help="Filter by file path pattern")
def audit_show(path: str, limit: int, tool: str | None, file_filter: str | None):
    """查看审计日志。"""
    entries = _load_audit_log(path)
    if entries is None:
        return

    # 应用过滤器
    if tool:
        entries = [e for e in entries if tool.lower() in e.get("tool_name", "").lower()]
    if file_filter:
        entries = [e for e in entries if file_filter.lower() in e.get("file_path", "").lower()]

    # 显示最近的条目
    recent = entries[-limit:]

    if not recent:
        console.print("[yellow]没有审计记录。[/]")
        return

    table = Table(title=f"审计日志 (最近 {len(recent)} 条，共 {len(entries)} 条)")
    table.add_column("时间", style="dim")
    table.add_column("工具", style="bold")
    table.add_column("操作")
    table.add_column("文件")
    table.add_column("状态")

    for entry in recent:
        timestamp = entry.get("timestamp", "")[:19]
        tool_name = entry.get("tool_name", "?")
        operation = entry.get("operation", "?")
        file_path = entry.get("file_path", "?")
        success = "[green]OK[/]" if entry.get("success") else "[red]FAIL[/]"
        table.add_row(timestamp, tool_name, operation, file_path, success)

    console.print(table)


@audit.command("stats")
@click.option("--path", default=".audit/audit.jsonl", help="Audit log file path")
def audit_stats(path: str):
    """审计统计汇总。"""
    entries = _load_audit_log(path)
    if entries is None:
        return

    if not entries:
        console.print("[yellow]没有审计记录。[/]")
        return

    total = len(entries)
    success = sum(1 for e in entries if e.get("success"))
    fail = total - success

    # 按工具统计
    tool_counts: dict[str, int] = {}
    for e in entries:
        tool = e.get("tool_name", "unknown")
        tool_counts[tool] = tool_counts.get(tool, 0) + 1

    # 按操作类型统计
    op_counts: dict[str, int] = {}
    for e in entries:
        op = e.get("operation", "unknown")
        op_counts[op] = op_counts.get(op, 0) + 1

    table = Table(title="审计统计")
    table.add_column("指标", style="bold")
    table.add_column("值")

    table.add_row("总操作数", str(total))
    table.add_row("成功", f"[green]{success}[/]")
    table.add_row("失败", f"[red]{fail}[/]" if fail else "0")
    table.add_row("成功率", f"{success/total*100:.1f}%")
    table.add_row("时间范围", f"{entries[0].get('timestamp', '?')[:10]} ~ {entries[-1].get('timestamp', '?')[:10]}")

    console.print(table)

    # 工具使用排行
    if tool_counts:
        tool_table = Table(title="工具使用排行")
        tool_table.add_column("工具", style="bold")
        tool_table.add_column("次数")
        tool_table.add_column("占比")
        for tool, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
            tool_table.add_row(tool, str(count), f"{count/total*100:.1f}%")
        console.print(tool_table)

    # 操作类型分布
    if op_counts:
        op_table = Table(title="操作类型分布")
        op_table.add_column("操作", style="bold")
        op_table.add_column("次数")
        for op, count in sorted(op_counts.items(), key=lambda x: -x[1]):
            op_table.add_row(op, str(count))
        console.print(op_table)


@audit.command("export")
@click.option("--path", default=".audit/audit.jsonl", help="Audit log file path")
@click.option("--output", default="audit_export.csv", help="Output CSV file path")
def audit_export(path: str, output: str):
    """导出审计日志为 CSV 文件。"""
    import csv

    entries = _load_audit_log(path)
    if entries is None:
        return

    if not entries:
        console.print("[yellow]没有审计记录可导出。[/]")
        return

    with open(output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["时间", "工具", "操作", "文件", "线程ID", "状态"])
        for entry in entries:
            writer.writerow([
                entry.get("timestamp", ""),
                entry.get("tool_name", ""),
                entry.get("operation", ""),
                entry.get("file_path", ""),
                entry.get("thread_id", ""),
                "OK" if entry.get("success") else "FAIL",
            ])

    console.print(f"[green]已导出 {len(entries)} 条记录到 {output}[/]")


@audit.command("verify")
@click.option("--path", default=".audit/audit.jsonl", help="Audit log file path")
def audit_verify(path: str):
    """校验审计日志的 HMAC 签名完整性。"""
    from .middleware.filesystem import AuditLog

    log_path = Path(path)
    if not log_path.exists():
        console.print(f"[yellow]审计日志不存在:[/] {path}")
        return

    audit_log = AuditLog(log_path=str(log_path))
    is_valid, errors = audit_log.verify_log()

    if is_valid:
        console.print("[green]OK 审计日志完整性校验通过[/]")
        if errors:
            console.print(f"  [dim]{errors[0]}[/]")
    else:
        console.print("[red]FAIL 审计日志完整性校验失败[/]")
        for error in errors[:10]:
            console.print(f"  [red]{error}[/]")
        if len(errors) > 10:
            console.print(f"  [dim]...共 {len(errors)} 个错误[/]")


# ============================================================
# evolution — 进化记忆管理
# ============================================================

@main.group()
def evolution():
    """进化记忆管理命令。"""
    pass


@evolution.command("list")
@click.option("--path", default=".evolution_memory", help="Evolution memory directory path")
@click.option("--limit", default=20, help="Number of recent entries to show")
@click.option("--type", "task_type", default=None, help="Filter by task type (code_writing, data_analysis, etc.)")
@click.option("--result", default=None, type=click.Choice(["success", "failure"]), help="Filter by result")
def evolution_list(path: str, limit: int, task_type: str | None, result: str | None):
    """查看积累的任务经验。"""
    from .evolution_memory.store import ExperienceStore

    store = ExperienceStore(store_path=path)
    experiences = store.list_experiences(limit=limit * 10)  # 多加载一些用于过滤

    if not experiences:
        console.print("[yellow]没有任务经验记录。[/]")
        console.print("使用 `create_agent(evolution_memory=True)` 开启进化记忆")
        return

    # 应用过滤器
    if task_type:
        experiences = [e for e in experiences if e.task_type == task_type]
    if result:
        experiences = [e for e in experiences if e.result == result]

    # 只显示 limit 条
    experiences = experiences[-limit:]

    table = Table(title=f"进化记忆 (最近 {len(experiences)} 条)")
    table.add_column("ID", style="dim")
    table.add_column("任务类型", style="bold")
    table.add_column("结果")
    table.add_column("耗时")
    table.add_column("任务描述")

    for exp in experiences:
        result_icon = "[green]✓[/]" if exp.result == "success" else "[red]✗[/]"
        duration = f"{exp.duration:.1f}s" if exp.duration else "-"
        task_preview = exp.task[:50] + "..." if len(exp.task) > 50 else exp.task
        table.add_row(exp.id, exp.task_type, result_icon, duration, task_preview)

    console.print(table)


@evolution.command("stats")
@click.option("--path", default=".evolution_memory", help="Evolution memory directory path")
def evolution_stats(path: str):
    """进化记忆统计汇总。"""
    from .evolution_memory.store import ExperienceStore

    store = ExperienceStore(store_path=path)
    experiences = store.list_experiences(limit=10000)

    if not experiences:
        console.print("[yellow]没有任务经验记录。[/]")
        return

    total = len(experiences)
    success = sum(1 for e in experiences if e.result == "success")
    failure = total - success

    # 按任务类型统计
    type_counts: dict[str, int] = {}
    for e in experiences:
        type_counts[e.task_type] = type_counts.get(e.task_type, 0) + 1

    # 计算平均耗时
    durations = [e.duration for e in experiences if e.duration and e.duration > 0]
    avg_duration = sum(durations) / len(durations) if durations else 0

    table = Table(title="进化记忆统计")
    table.add_column("指标", style="bold")
    table.add_column("值")

    table.add_row("总任务数", str(total))
    table.add_row("成功", f"[green]{success}[/]")
    table.add_row("失败", f"[red]{failure}[/]" if failure else "0")
    table.add_row("成功率", f"{success/total*100:.1f}%")
    table.add_row("平均耗时", f"{avg_duration:.1f}s")

    console.print(table)

    # 任务类型分布
    if type_counts:
        type_table = Table(title="任务类型分布")
        type_table.add_column("类型", style="bold")
        type_table.add_column("次数")
        type_table.add_column("成功率")

        for task_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            type_success = sum(1 for e in experiences if e.task_type == task_type and e.result == "success")
            success_rate = type_success / count * 100 if count > 0 else 0
            type_table.add_row(task_type, str(count), f"{success_rate:.1f}%")

        console.print(type_table)


@evolution.command("show")
@click.argument("experience_id")
@click.option("--path", default=".evolution_memory", help="Evolution memory directory path")
def evolution_show(experience_id: str, path: str):
    """查看指定经验的详细信息。"""
    from .evolution_memory.store import ExperienceStore

    store = ExperienceStore(store_path=path)
    experience = store.get_experience(experience_id)

    if not experience:
        console.print(f"[red]经验不存在:[/] {experience_id}")
        console.print("使用 `hz-agent evolution list` 查看所有经验")
        return

    # 显示详细信息
    console.print(f"[bold]经验详情: {experience.id}[/bold]\n")

    table = Table(show_header=False)
    table.add_column("字段", style="bold")
    table.add_column("值")

    table.add_row("任务类型", experience.task_type)
    table.add_row("结果", "[green]成功[/]" if experience.result == "success" else "[red]失败[/]")
    table.add_row("耗时", f"{experience.duration:.1f}s" if experience.duration else "-")
    table.add_row("任务描述", experience.task)
    table.add_row("策略", experience.strategy or "-")
    table.add_row("使用工具", ", ".join(experience.tools_used) if experience.tools_used else "-")

    console.print(table)

    if experience.issues:
        console.print("\n[bold yellow]问题:[/]")
        for issue in experience.issues:
            console.print(f"  - {issue}")

    if experience.lessons:
        console.print("\n[bold green]经验教训:[/]")
        for lesson in experience.lessons:
            console.print(f"  - {lesson}")


@evolution.command("clear")
@click.option("--path", default=".evolution_memory", help="Evolution memory directory path")
@click.option("--confirm", is_flag=True, help="Skip confirmation")
def evolution_clear(path: str, confirm: bool):
    """清空所有进化记忆。"""
    memory_path = Path(path)
    if not memory_path.exists():
        console.print(f"[yellow]进化记忆目录不存在:[/] {path}")
        return

    files = list(memory_path.glob("*.json"))
    if not files:
        console.print("[yellow]没有进化记忆需要清理。[/]")
        return

    if not confirm:
        console.print(f"[bold yellow]即将删除 {len(files)} 个经验文件[/]")
        if not click.confirm("确认删除？"):
            console.print("已取消。")
            return

    for f in files:
        f.unlink()

    console.print(f"[green]已删除 {len(files)} 个经验文件。[/]")


@evolution.command("similar")
@click.argument("query")
@click.option("--path", default=".evolution_memory", help="Evolution memory directory path")
@click.option("--limit", default=5, help="Max results")
def evolution_similar(query: str, path: str, limit: int):
    """搜索相似任务经验。"""
    from .evolution_memory.store import ExperienceStore

    store = ExperienceStore(store_path=path)
    similar = store.get_similar_experiences(task=query, limit=limit)

    if not similar:
        console.print(f"[yellow]未找到与 '{query}' 相似的经验。[/]")
        return

    table = Table(title=f"相似经验: '{query}'")
    table.add_column("ID", style="dim")
    table.add_column("类型", style="bold")
    table.add_column("结果")
    table.add_column("任务描述")

    for exp in similar:
        result_icon = "[green]✓[/]" if exp.result == "success" else "[red]✗[/]"
        task_preview = exp.task[:60] + "..." if len(exp.task) > 60 else exp.task
        table.add_row(exp.id, exp.task_type, result_icon, task_preview)

    console.print(table)


# ============================================================
# 辅助函数
# ============================================================

def _load_audit_log(path: str) -> list[dict] | None:
    """加载审计日志文件。"""
    log_path = Path(path)
    if not log_path.exists():
        console.print(f"[yellow]审计日志不存在:[/] {path}")
        console.print("使用 `create_agent(filesystem=True)` 开启文件审计")
        return None

    entries = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return entries


if __name__ == "__main__":
    main()
