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
        console.print(f"[bold red]Error:[/] {e}", err=True)
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
        from .config import DEFAULT_MODEL, DEEPSEEK_BASE_URL
        table.add_row("Default Model", DEFAULT_MODEL)
        table.add_row("API Base URL", DEEPSEEK_BASE_URL)
    except Exception:
        table.add_row("Config", "Not loaded")

    console.print(table)


if __name__ == "__main__":
    main()
