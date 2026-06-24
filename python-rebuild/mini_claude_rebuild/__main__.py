from __future__ import annotations

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv

from . import __version__
from .agent import Agent
from .ui import print_error


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
        "--model",
        default=None,
        help="Model to use for the chat request.",
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Message to send to the model.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    if args.version:
        print(f"mini-claude-rebuild {__version__}")
        return

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print_error("DEEPSEEK_API_KEY is required. Put it in .env or set it in your shell.")
        sys.exit(1)

    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = args.model or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
    prompt = " ".join(args.prompt) or "hello"
    agent = Agent(api_key=api_key, base_url=base_url, model=model)
    asyncio.run(agent.chat(prompt))


if __name__ == "__main__":
    main()
