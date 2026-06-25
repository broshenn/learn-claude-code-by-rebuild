from __future__ import annotations

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv

from . import __version__
from .agent import Agent
from .memory import list_memories
from .session import get_latest_session_id, load_session
from .skills import discover_skills, get_skill_by_name, resolve_skill_prompt
from .ui import print_error, print_info, print_user_prompt, print_welcome


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mini-claude-rebuild",
        description="A step-by-step Python rebuild of Mini Claude Code.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show the current rebuild version.",
    )
    parser.add_argument(
        "--yolo",
        "-y",
        action="store_true",
        help="Skip permission prompts.",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Read-only planning mode.",
    )
    parser.add_argument(
        "--accept-edits",
        action="store_true",
        help="Auto-approve file edits.",
    )
    parser.add_argument(
        "--dont-ask",
        action="store_true",
        help="Auto-deny tools that need confirmation.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model to use for the chat request.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume the latest saved session.",
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Message to send to the model.",
    )
    return parser.parse_args()


def resolve_permission_mode(args: argparse.Namespace) -> str:
    if args.yolo:
        return "bypassPermissions"
    if args.plan:
        return "plan"
    if args.accept_edits:
        return "acceptEdits"
    if args.dont_ask:
        return "dontAsk"
    return "default"


def resolve_api_config(args: argparse.Namespace) -> dict:
    if os.environ.get("DEEPSEEK_API_KEY"):
        return {
            "api_key": os.environ["DEEPSEEK_API_KEY"],
            "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            "model": args.model or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            "use_openai": True,
        }

    if os.environ.get("OPENAI_API_KEY"):
        return {
            "api_key": os.environ["OPENAI_API_KEY"],
            "base_url": os.environ.get("OPENAI_BASE_URL"),
            "model": args.model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "use_openai": True,
        }

    if os.environ.get("ANTHROPIC_API_KEY"):
        return {
            "api_key": os.environ["ANTHROPIC_API_KEY"],
            "base_url": os.environ.get("ANTHROPIC_BASE_URL"),
            "model": args.model or os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-6"),
            "use_openai": False,
        }

    return {}


async def run_repl(agent: Agent) -> None:
    """Interactive read-eval-print loop for multi-turn chat."""
    async def confirm_fn(message: str) -> bool:
        try:
            answer = input("Allow? (y/n): ")
        except EOFError:
            return False
        return answer.lower().startswith("y")

    agent.set_confirm_fn(confirm_fn)
    print_welcome()

    while True:
        print_user_prompt()
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!\n")
            break

        user_input = line.strip()
        if not user_input:
            continue
        if user_input in ("exit", "quit"):
            print("\nBye!\n")
            break
        if user_input == "/clear":
            agent.clear_history()
            continue
        if user_input == "/compact":
            try:
                await agent.compact()
            except Exception as exc:
                print_error(str(exc))
            continue
        if user_input == "/memory":
            memories = list_memories()
            if not memories:
                print_info("No memories saved yet.")
            else:
                print_info(f"{len(memories)} memories:")
                for memory in memories:
                    print(f"  [{memory.type}] {memory.name} - {memory.description}")
            continue
        if user_input == "/skills":
            skills = discover_skills()
            if not skills:
                print_info("No skills found. Add skills to .claude/skills/<name>/SKILL.md")
            else:
                print_info(f"{len(skills)} skills:")
                for skill in skills:
                    prefix = f"/{skill.name}" if skill.user_invocable else skill.name
                    print(f"  {prefix} ({skill.source}) - {skill.description}")
            continue
        if user_input.startswith("/"):
            space_index = user_input.find(" ")
            skill_name = user_input[1:space_index] if space_index > 0 else user_input[1:]
            skill_args = user_input[space_index + 1:] if space_index > 0 else ""
            skill = get_skill_by_name(skill_name)
            if skill and skill.user_invocable:
                print_info(f"Invoking skill: {skill.name}")
                await agent.chat(resolve_skill_prompt(skill, skill_args))
                continue

        try:
            await agent.chat(user_input)
        except Exception as exc:
            print_error(str(exc))


def main() -> None:
    load_dotenv()
    args = parse_args()
    if args.version:
        print(f"mini-claude-rebuild {__version__}")
        return

    api_config = resolve_api_config(args)
    if not api_config:
        print_error(
            "API key is required. Set DEEPSEEK_API_KEY for DeepSeek, "
            "OPENAI_API_KEY for OpenAI-compatible APIs, or ANTHROPIC_API_KEY for Anthropic."
        )
        sys.exit(1)

    permission_mode = resolve_permission_mode(args)
    agent = Agent(
        api_key=api_config["api_key"],
        base_url=api_config["base_url"],
        model=api_config["model"],
        use_openai=api_config["use_openai"],
        permission_mode=permission_mode,
    )

    if args.resume:
        session_id = get_latest_session_id()
        if session_id:
            session = load_session(session_id)
            if session:
                agent.restore_session(session)
            else:
                print_info("No session found to resume.")
        else:
            print_info("No previous sessions found.")

    prompt = " ".join(args.prompt) if args.prompt else None

    if prompt:
        asyncio.run(agent.chat(prompt))
    else:
        asyncio.run(run_repl(agent))


if __name__ == "__main__":
    main()
