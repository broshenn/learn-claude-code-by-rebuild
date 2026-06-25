from __future__ import annotations

import sys


def print_welcome() -> None:
    print()
    print("  Mini Claude Rebuild - a minimal coding agent")
    print("  Type your request, or 'exit' to quit.")
    print("  Commands: /clear /plan /compact /memory /skills")
    print()


def print_user_prompt() -> None:
    print()
    print("> ", end="")


def print_assistant_text(text: str) -> None:
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.flush()


def print_assistant_delta(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def print_tool_call(name: str, arguments: dict) -> None:
    summary = get_tool_summary(name, arguments)
    suffix = f" {summary}" if summary else ""
    print(f"\n[tool:{name}]{suffix}")


def print_tool_result(name: str, result: str) -> None:
    if name in {"write_file", "edit_file"} and not result.startswith("Error"):
        print_file_change_result(result)
        return

    max_length = 1200
    if len(result) > max_length:
        result = result[:max_length] + f"\n... ({len(result)} chars total)"
    print(result)


def print_file_change_result(result: str) -> None:
    lines = result.splitlines()
    if not lines:
        return

    print(lines[0])
    for line in lines[1:40]:
        print(line)
    if len(lines) > 40:
        print(f"... ({len(lines) - 40} more lines)")


def print_error(message: str) -> None:
    print(f"Error: {message}")


def print_info(message: str) -> None:
    print(message)


def print_confirmation(message: str) -> None:
    print()
    print(f"Permission required: {message}")


def print_plan_for_approval(plan_content: str) -> None:
    print()
    print("Plan for approval")
    print("=" * 50)
    lines = plan_content.splitlines()
    for line in lines[:80]:
        print(line)
    if len(lines) > 80:
        print(f"... ({len(lines) - 80} more lines)")
    print("=" * 50)


def print_plan_approval_options() -> None:
    print("Choose an option:")
    print("  1. Approve and execute with auto-approved edits")
    print("  2. Approve, but keep manual confirmations")
    print("  3. Keep planning")


def print_sub_agent_start(agent_type: str, description: str) -> None:
    print()
    print(f"[sub-agent:{agent_type}] {description}")


def print_sub_agent_end(agent_type: str, description: str) -> None:
    suffix = f" {description}" if description else ""
    print(f"[sub-agent:{agent_type}] completed{suffix}")


def get_tool_summary(name: str, arguments: dict) -> str:
    if name in {"read_file", "write_file", "edit_file"}:
        return arguments.get("file_path", "")
    if name == "list_files":
        return arguments.get("pattern", "")
    if name == "grep_search":
        return f'"{arguments.get("pattern", "")}" in {arguments.get("path", ".")}'
    if name == "run_shell":
        command = arguments.get("command", "")
        return command[:60] + "..." if len(command) > 60 else command
    if name == "agent":
        return f'[{arguments.get("type", "general")}] {arguments.get("description", "")}'
    return ""
