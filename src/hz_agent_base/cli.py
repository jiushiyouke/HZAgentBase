"""CLI entry point for HZAgentBase."""

from __future__ import annotations

import sys
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from .agent import create_agent, run_agent
from .permissions import PermissionSettings, PermissionMode


console = Console()


@click.group()
@click.version_option()
def main():
    """HZAgentBase - Agent Harness CLI."""
    pass


@main.command()
@click.option("--model", default=None, help="LLM model (default: deepseek-v4-flash)")
@click.option("--auto", is_flag=True, help="Full auto mode (no confirmations)")
@click.option("--plan", is_flag=True, help="Plan mode (read-only)")
@click.option("--memory", default=None, help="Path to memory directory")
@click.option("--rules", default=None, help="Path to shared rules directory")
@click.option("--prompt", default=None, help="System prompt (string or file/directory path)")
@click.option("--filesystem", is_flag=True, help="Enable file operation audit")
def chat(
    model: str | None,
    auto: bool,
    plan: bool,
    memory: str | None,
    rules: str | None,
    prompt: str | None,
    filesystem: bool,
):
    """Start an interactive chat session."""
    mode = PermissionMode.FULL_AUTO if auto else (PermissionMode.PLAN if plan else PermissionMode.DEFAULT)

    agent = create_agent(
        model=model,
        system_prompt=prompt,
        rules=[rules] if rules else None,
        permissions=PermissionSettings(mode=mode),
        memory_path=memory,
        filesystem=filesystem,
    )

    console.print("[bold green]HZAgentBase Chat[/bold green]")
    model_name = model or "deepseek-v4-flash"
    console.print(f"Model: {model_name} | Mode: {mode.value}")
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


@main.command()
@click.argument("prompt")
@click.option("--model", default=None, help="LLM model")
@click.option("--auto", is_flag=True, help="Full auto mode")
@click.option("--thread", default=None, help="Thread ID for session isolation")
def run(prompt: str, model: str | None, auto: bool, thread: str | None):
    """Run a single prompt and print the response."""
    mode = PermissionMode.FULL_AUTO if auto else PermissionMode.DEFAULT

    agent = create_agent(
        model=model,
        permissions=PermissionSettings(mode=mode),
    )

    try:
        result = run_agent(agent, prompt, thread_id=thread)
        messages = result.get("messages", [])
        for msg in messages:
            if hasattr(msg, "type") and msg.type == "ai":
                console.print(msg.content)
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        sys.exit(1)


@main.command()
def version():
    """Show version and environment info."""
    from . import __version__

    table = Table(title="HZAgentBase")
    table.add_column("Key", style="bold")
    table.add_column("Value")
    table.add_row("Version", __version__)

    try:
        from .config import DEFAULT_MODEL, MODEL_BASE_URL
        table.add_row("Default Model", DEFAULT_MODEL)
        table.add_row("API Base URL", MODEL_BASE_URL)
    except Exception:
        table.add_row("Config", "Not loaded")

    console.print(table)


@main.group()
def memory():
    """Memory management commands."""
    pass


@memory.command("list")
@click.option("--path", default=".memory", help="Memory directory path")
def memory_list(path: str):
    """List all stored memories."""
    from pathlib import Path

    memory_path = Path(path)
    if not memory_path.exists():
        console.print(f"[yellow]Memory directory not found:[/] {path}")
        return

    table = Table(title=f"Memories ({path})")
    table.add_column("Name", style="bold")
    table.add_column("File")

    files = sorted(memory_path.glob("*.md"))
    count = 0
    for f in files:
        if f.name == "MEMORY.md":
            continue
        table.add_row(f.stem, f.name)
        count += 1

    if count == 0:
        console.print("[yellow]No memories found.[/]")
    else:
        console.print(table)
        console.print(f"\nTotal: {count} memories")


@main.command()
@click.option("--path", default=".audit/audit.jsonl", help="Audit log file path")
@click.option("--limit", default=20, help="Number of recent entries to show")
@click.option("--tool", default=None, help="Filter by tool name")
@click.option("--file", "file_filter", default=None, help="Filter by file path pattern")
def audit(path: str, limit: int, tool: str | None, file_filter: str | None):
    """View file operation audit logs."""
    import json
    from pathlib import Path

    log_path = Path(path)
    if not log_path.exists():
        console.print(f"[yellow]Audit log not found:[/] {path}")
        console.print("Enable file audit with: create_agent(filesystem=True)")
        return

    # 读取所有日志条目
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

    # 应用过滤器
    if tool:
        entries = [e for e in entries if tool.lower() in e.get("tool_name", "").lower()]
    if file_filter:
        entries = [e for e in entries if file_filter.lower() in e.get("file_path", "").lower()]

    # 显示最近的条目
    recent = entries[-limit:]

    if not recent:
        console.print("[yellow]No audit entries found.[/]")
        return

    table = Table(title=f"Audit Log (last {len(recent)} of {len(entries)})")
    table.add_column("Time", style="dim")
    table.add_column("Tool", style="bold")
    table.add_column("Operation")
    table.add_column("File")
    table.add_column("Status")

    for entry in recent:
        timestamp = entry.get("timestamp", "")[:19]  # 截断毫秒
        tool_name = entry.get("tool_name", "?")
        operation = entry.get("operation", "?")
        file_path = entry.get("file_path", "?")
        success = "[green]OK[/]" if entry.get("success") else "[red]FAIL[/]"
        table.add_row(timestamp, tool_name, operation, file_path, success)

    console.print(table)


if __name__ == "__main__":
    main()
