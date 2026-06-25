from __future__ import annotations

import json
from pathlib import Path

from .frontmatter import parse_frontmatter
from .tools import tool_definitions

READ_ONLY_TOOLS = {"read_file", "list_files", "grep_search"}

EXPLORE_PROMPT = """You are a read-only codebase exploration agent.

You can search, list, and read files, but you must not modify anything.
Return concise findings with relevant file paths."""

PLAN_PROMPT = """You are a read-only planning agent.

Analyze the codebase and return a structured implementation plan.
Do not modify files or run shell commands that change state."""

GENERAL_PROMPT = """You are a focused sub-agent for Mini Claude Code.

Complete the delegated task with the available tools and return a concise report.
Keep your work scoped to the requested task."""

_cached_custom_agents: dict[str, dict] | None = None


def _tool_name(tool: dict) -> str:
    return tool["function"]["name"]


def _discover_custom_agents() -> dict[str, dict]:
    global _cached_custom_agents
    if _cached_custom_agents is not None:
        return _cached_custom_agents

    agents: dict[str, dict] = {}
    _load_agents_from_dir(Path.home() / ".claude" / "agents", agents)
    _load_agents_from_dir(Path.cwd() / ".claude" / "agents", agents)
    _cached_custom_agents = agents
    return agents


def _load_agents_from_dir(directory: Path, agents: dict[str, dict]) -> None:
    if not directory.is_dir():
        return

    for path in sorted(directory.glob("*.md")):
        try:
            parsed = parse_frontmatter(path.read_text(encoding="utf-8"))
        except OSError:
            continue

        name = parsed.meta.get("name") or path.stem
        agents[name] = {
            "name": name,
            "description": parsed.meta.get("description", ""),
            "allowed_tools": _parse_allowed_tools(parsed.meta.get("allowed-tools")),
            "system_prompt": parsed.body,
        }


def _parse_allowed_tools(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            raw = raw.strip("[]")
    return [item.strip() for item in raw.split(",") if item.strip()]


def get_sub_agent_config(agent_type: str) -> dict:
    custom = _discover_custom_agents().get(agent_type)
    if custom:
        if custom["allowed_tools"]:
            tools = [tool for tool in tool_definitions if _tool_name(tool) in custom["allowed_tools"]]
        else:
            tools = [tool for tool in tool_definitions if _tool_name(tool) != "agent"]
        return {"system_prompt": custom["system_prompt"], "tools": tools}

    read_only_tools = [tool for tool in tool_definitions if _tool_name(tool) in READ_ONLY_TOOLS]
    if agent_type == "explore":
        return {"system_prompt": EXPLORE_PROMPT, "tools": read_only_tools}
    if agent_type == "plan":
        return {"system_prompt": PLAN_PROMPT, "tools": read_only_tools}
    return {
        "system_prompt": GENERAL_PROMPT,
        "tools": [tool for tool in tool_definitions if _tool_name(tool) != "agent"],
    }


def get_available_agent_types() -> list[dict[str, str]]:
    agent_types = [
        {"name": "explore", "description": "Read-only codebase search and exploration"},
        {"name": "plan", "description": "Read-only implementation planning"},
        {"name": "general", "description": "General focused task execution"},
    ]
    for name, config in _discover_custom_agents().items():
        agent_types.append({"name": name, "description": config["description"]})
    return agent_types


def build_agent_descriptions() -> str:
    custom_types = get_available_agent_types()[3:]
    if not custom_types:
        return ""

    lines = ["# Custom Agent Types", ""]
    for agent_type in custom_types:
        lines.append(f"- {agent_type['name']}: {agent_type['description']}")
    return "\n".join(lines)


def reset_agent_cache() -> None:
    global _cached_custom_agents
    _cached_custom_agents = None
