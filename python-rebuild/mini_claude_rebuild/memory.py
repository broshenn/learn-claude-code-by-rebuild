from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .frontmatter import format_frontmatter, parse_frontmatter

VALID_TYPES = {"user", "feedback", "project", "reference"}
MAX_INDEX_LINES = 200
MAX_INDEX_BYTES = 25_000
MAX_MEMORY_BYTES_PER_FILE = 4096


@dataclass
class MemoryEntry:
    name: str
    description: str
    type: str
    filename: str
    content: str


@dataclass
class MemoryHeader:
    filename: str
    file_path: str
    description: str
    type: str


def _project_hash() -> str:
    return hashlib.sha256(str(Path.cwd()).encode("utf-8")).hexdigest()[:16]


def get_memory_dir() -> Path:
    memory_dir = Path.home() / ".mini-claude-rebuild" / "projects" / _project_hash() / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


def _index_path() -> Path:
    return get_memory_dir() / "MEMORY.md"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:40] or "memory"


def save_memory(name: str, description: str, type: str, content: str) -> str:
    memory_type = type if type in VALID_TYPES else "project"
    filename = f"{memory_type}_{_slugify(name)}.md"
    text = format_frontmatter(
        {"name": name, "description": description, "type": memory_type},
        content,
    )
    (get_memory_dir() / filename).write_text(text, encoding="utf-8")
    update_memory_index()
    return filename


def list_memories() -> list[MemoryEntry]:
    memory_dir = get_memory_dir()
    entries: list[MemoryEntry] = []
    for path in sorted(memory_dir.glob("*.md")):
        if path.name == "MEMORY.md":
            continue
        try:
            parsed = parse_frontmatter(path.read_text(encoding="utf-8"))
        except OSError:
            continue

        name = parsed.meta.get("name")
        memory_type = parsed.meta.get("type", "project")
        if not name:
            continue
        if memory_type not in VALID_TYPES:
            memory_type = "project"

        entries.append(
            MemoryEntry(
                name=name,
                description=parsed.meta.get("description", ""),
                type=memory_type,
                filename=path.name,
                content=parsed.body,
            )
        )

    entries.sort(key=lambda entry: (memory_dir / entry.filename).stat().st_mtime, reverse=True)
    return entries


def update_memory_index() -> None:
    lines = ["# Memory Index", ""]
    for memory in list_memories():
        lines.append(f"- **[{memory.name}]({memory.filename})** ({memory.type}) - {memory.description}")
    _index_path().write_text("\n".join(lines), encoding="utf-8")


def load_memory_index() -> str:
    path = _index_path()
    if not path.exists():
        return ""

    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    if len(lines) > MAX_INDEX_LINES:
        content = "\n".join(lines[:MAX_INDEX_LINES]) + "\n\n[... truncated, too many memory entries ...]"
    if len(content.encode("utf-8")) > MAX_INDEX_BYTES:
        content = content[:MAX_INDEX_BYTES] + "\n\n[... truncated, index too large ...]"
    return content


def scan_memory_headers() -> list[MemoryHeader]:
    headers: list[MemoryHeader] = []
    for path in get_memory_dir().glob("*.md"):
        if path.name == "MEMORY.md":
            continue
        try:
            first_lines = "\n".join(path.read_text(encoding="utf-8").splitlines()[:30])
            parsed = parse_frontmatter(first_lines)
        except OSError:
            continue

        memory_type = parsed.meta.get("type", "project")
        if memory_type not in VALID_TYPES:
            memory_type = "project"
        headers.append(
            MemoryHeader(
                filename=path.name,
                file_path=str(path),
                description=parsed.meta.get("description", ""),
                type=memory_type,
            )
        )

    headers.sort(key=lambda header: header.filename)
    return headers


def select_relevant_memories(query: str, limit: int = 5) -> list[MemoryEntry]:
    query_words = set(re.findall(r"[a-z0-9]+", query.lower()))
    scored: list[tuple[int, MemoryEntry]] = []
    for memory in list_memories():
        haystack = f"{memory.name} {memory.description} {memory.content}".lower()
        score = sum(1 for word in query_words if word in haystack)
        if score:
            scored.append((score, memory))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [memory for _, memory in scored[:limit]]


def format_memories_for_injection(memories: list[MemoryEntry]) -> str:
    parts: list[str] = []
    for memory in memories:
        content = memory.content
        if len(content.encode("utf-8")) > MAX_MEMORY_BYTES_PER_FILE:
            content = content[:MAX_MEMORY_BYTES_PER_FILE] + "\n\n[... truncated, memory file too large ...]"
        parts.append(
            f"<system-reminder>\n"
            f"Memory: {memory.filename} ({memory.type}) - {memory.description}\n\n"
            f"{content}\n"
            f"</system-reminder>"
        )
    return "\n\n".join(parts)


def build_memory_prompt_section() -> str:
    memory_dir = get_memory_dir()
    index = load_memory_index()
    index_text = index if index else "(No memories saved yet.)"
    return f"""
# Memory System

You have a persistent file-based memory system at `{memory_dir}`.

Memory files are Markdown files with frontmatter:

```markdown
---
name: memory name
description: one-line description
type: user|feedback|project|reference
---
Memory content here.
```

Use memory for durable user preferences, feedback, project facts, and reference notes.
When saving memory, write a `.md` file under `{memory_dir}`. The `MEMORY.md` index is maintained automatically.

## Current Memory Index
{index_text}"""
