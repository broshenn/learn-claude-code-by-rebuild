from __future__ import annotations

import fnmatch
import re
from pathlib import Path


tool_definitions = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file and return it with line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to read.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files that match a glob pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match, such as '**/*.py'.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Base directory to search from. Defaults to current directory.",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Search for a regex pattern in text files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory or file to search in. Defaults to current directory.",
                    },
                    "include": {
                        "type": "string",
                        "description": "Optional file glob to include, such as '*.py'.",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
]


def read_file(file_path: str) -> str:
    content = Path(file_path).read_text(encoding="utf-8")
    lines = content.splitlines()
    if not lines:
        return "(empty file)"
    return "\n".join(f"{line_number:4d} | {line}" for line_number, line in enumerate(lines, start=1))


def list_files(pattern: str, path: str = ".") -> str:
    base_path = Path(path)
    matches = sorted(p for p in base_path.glob(pattern) if p.is_file())
    if not matches:
        return "(no files found)"
    return "\n".join(str(p) for p in matches[:200])


def grep_search(pattern: str, path: str = ".", include: str | None = None) -> str:
    root = Path(path)
    files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
    regex = re.compile(pattern)
    results: list[str] = []

    for file_path in files:
        if include and not fnmatch.fnmatch(file_path.name, include):
            continue
        try:
            for line_number, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), start=1):
                if regex.search(line):
                    results.append(f"{file_path}:{line_number}: {line}")
                    if len(results) >= 200:
                        return "\n".join(results)
        except UnicodeDecodeError:
            continue
        except OSError as error:
            results.append(f"{file_path}: error reading file: {error}")

    if not results:
        return "(no matches found)"
    return "\n".join(results)


async def execute_tool(name: str, arguments: dict) -> str:
    if name == "read_file":
        return read_file(arguments["file_path"])
    if name == "list_files":
        return list_files(arguments["pattern"], arguments.get("path", "."))
    if name == "grep_search":
        return grep_search(arguments["pattern"], arguments.get("path", "."), arguments.get("include"))
    return f"Unknown tool: {name}"
