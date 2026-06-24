from __future__ import annotations

import fnmatch
import re
import subprocess
from pathlib import Path

from .memory import get_memory_dir, update_memory_index

PermissionMode = str

READ_TOOLS = {"read_file", "list_files", "grep_search"}
EDIT_TOOLS = {"write_file", "edit_file"}
CONFIRM_TOOLS = EDIT_TOOLS | {"run_shell"}


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
            "name": "write_file",
            "description": "Write content to a file. Creates parent directories if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to write.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file.",
                    },
                },
                "required": ["file_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit a file by replacing one unique old_string with new_string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to edit.",
                    },
                    "old_string": {
                        "type": "string",
                        "description": "Exact text to find. It must appear once.",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "Replacement text.",
                    },
                },
                "required": ["file_path", "old_string", "new_string"],
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
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a shell command and return stdout, stderr, or failure details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute.",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Timeout in milliseconds. Defaults to 30000.",
                    },
                },
                "required": ["command"],
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


def write_file(file_path: str, content: str) -> str:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _auto_update_memory_index(path)

    lines = content.split("\n")
    preview = "\n".join(f"{line_number:4d} | {line}" for line_number, line in enumerate(lines[:30], start=1))
    truncation = f"\n  ... ({len(lines)} lines total)" if len(lines) > 30 else ""
    return f"Successfully wrote to {file_path} ({len(lines)} lines)\n\n{preview}{truncation}"


def _auto_update_memory_index(path: Path) -> None:
    try:
        memory_dir = get_memory_dir().resolve()
        resolved = path.resolve()
        if resolved.parent == memory_dir and resolved.name != "MEMORY.md" and resolved.suffix == ".md":
            update_memory_index()
    except Exception:
        return


def normalize_quotes(text: str) -> str:
    text = re.sub("[\u2018\u2019\u2032]", "'", text)
    text = re.sub('[\u201c\u201d\u2033]', '"', text)
    return text


def find_actual_string(file_content: str, search_string: str) -> str | None:
    if search_string in file_content:
        return search_string

    normalized_file = normalize_quotes(file_content)
    normalized_search = normalize_quotes(search_string)
    index = normalized_file.find(normalized_search)
    if index == -1:
        return None
    return file_content[index:index + len(search_string)]


def generate_diff(old_content: str, old_string: str, new_string: str) -> str:
    before_change = old_content.split(old_string)[0]
    line_number = before_change.count("\n") + 1
    old_lines = old_string.split("\n")
    new_lines = new_string.split("\n")

    parts = [f"@@ -{line_number},{len(old_lines)} +{line_number},{len(new_lines)} @@"]
    parts.extend(f"- {line}" for line in old_lines)
    parts.extend(f"+ {line}" for line in new_lines)
    return "\n".join(parts)


def edit_file(file_path: str, old_string: str, new_string: str) -> str:
    path = Path(file_path)
    content = path.read_text(encoding="utf-8")

    actual = find_actual_string(content, old_string)
    if actual is None:
        return f"Error: old_string not found in {file_path}"

    count = content.count(actual)
    if count > 1:
        return f"Error: old_string found {count} times in {file_path}. Must be unique."

    path.write_text(content.replace(actual, new_string, 1), encoding="utf-8")
    diff = generate_diff(content, actual, new_string)
    quote_note = " (matched via quote normalization)" if actual != old_string else ""
    return f"Successfully edited {file_path}{quote_note}\n\n{diff}"


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


def run_shell(command: str, timeout: int = 30000) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout / 1000,
        )
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}ms"
    except Exception as error:
        return f"Error: {error}"

    if result.returncode != 0:
        stdout = f"\nStdout: {result.stdout}" if result.stdout else ""
        stderr = f"\nStderr: {result.stderr}" if result.stderr else ""
        return f"Command failed (exit code {result.returncode}){stdout}{stderr}"

    return result.stdout or "(no output)"


def check_permission(name: str, arguments: dict, mode: PermissionMode = "default") -> dict:
    if mode == "bypassPermissions":
        return {"action": "allow"}

    if name in READ_TOOLS:
        return {"action": "allow"}

    if mode == "plan" and name in CONFIRM_TOOLS:
        return {"action": "deny", "message": f"Blocked in plan mode: {name}"}

    if mode == "acceptEdits" and name in EDIT_TOOLS:
        return {"action": "allow"}

    if name in CONFIRM_TOOLS:
        message = _permission_message(name, arguments)
        if mode == "dontAsk":
            return {"action": "deny", "message": f"Auto-denied (dontAsk mode): {message}"}
        return {"action": "confirm", "message": message}

    return {"action": "allow"}


def _permission_message(name: str, arguments: dict) -> str:
    if name == "write_file":
        return f"write file: {arguments.get('file_path', '')}"
    if name == "edit_file":
        return f"edit file: {arguments.get('file_path', '')}"
    if name == "run_shell":
        return f"run shell: {arguments.get('command', '')}"
    return name


async def execute_tool(name: str, arguments: dict) -> str:
    if name == "read_file":
        return read_file(arguments["file_path"])
    if name == "write_file":
        return write_file(arguments["file_path"], arguments["content"])
    if name == "edit_file":
        return edit_file(arguments["file_path"], arguments["old_string"], arguments["new_string"])
    if name == "list_files":
        return list_files(arguments["pattern"], arguments.get("path", "."))
    if name == "grep_search":
        return grep_search(arguments["pattern"], arguments.get("path", "."), arguments.get("include"))
    if name == "run_shell":
        return run_shell(arguments["command"], int(arguments.get("timeout", 30000)))
    return f"Unknown tool: {name}"
