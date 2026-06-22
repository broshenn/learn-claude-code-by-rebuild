from __future__ import annotations

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
    }
]


def read_file(file_path: str) -> str:
    content = Path(file_path).read_text(encoding="utf-8")
    lines = content.splitlines()
    if not lines:
        return "(empty file)"
    return "\n".join(f"{line_number:4d} | {line}" for line_number, line in enumerate(lines, start=1))


async def execute_tool(name: str, arguments: dict) -> str:
    if name == "read_file":
        return read_file(arguments["file_path"])
    return f"Unknown tool: {name}"
