"""CLI entry point for HZAgentBase."""

from __future__ import annotations

import sys
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown

from .agent import create_agent
from .permissions import PermissionSettings, PermissionMode


console = Console()


@click.group()
@click.version_option()
def main():
    """HZAgentBase - Agent Harness CLI."""
    pass


@main.command()
@click.option("--model", default="deepseek-v4-flash", help="LLM model to use")
@click.option("--auto", is_flag=True, help="Full auto mode (no confirmations)")
@click.option("--plan", is_flag=True, help="Plan mode (read-only)")
@click.option("--memory", default=None, help="Path to memory directory")
def chat(model: str, auto: bool, plan: bool, memory: Optional[str]):
    """Start an interactive chat session."""
    # Determine permission mode
    if auto:
        mode = PermissionMode.FULL_AUTO
    elif plan:
        mode = PermissionMode.PLAN
    else:
        mode = PermissionMode.DEFAULT

    agent = create_agent(
        model=model,
        permissions=PermissionSettings(mode=mode),
        memory_path=memory,
    )

    console.print("[bold green]HZAgentBase Chat[/bold green]")
    console.print(f"Model: {model} | Mode: {mode.value}")
    console.print("Type 'exit' or 'quit' to end the session.\n")

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
            # Run the agent
            result = agent.invoke({"messages": [{"role": "user", "content": user_input}]})

            # Extract and display the response
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
@click.option("--model", default="deepseek-v4-flash", help="LLM model to use")
@click.option("--auto", is_flag=True, help="Full auto mode")
def run(prompt: str, model: str, auto: bool):
    """Run a single prompt and print the response."""
    mode = PermissionMode.FULL_AUTO if auto else PermissionMode.DEFAULT

    agent = create_agent(
        model=model,
        permissions=PermissionSettings(mode=mode),
    )

    try:
        result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
        messages = result.get("messages", [])
        for msg in messages:
            if hasattr(msg, "type") and msg.type == "ai":
                console.print(msg.content)
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
