"""Simple YAML-style frontmatter parser for memory and skills files."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FrontmatterResult:
    meta: dict[str, str] = field(default_factory=dict)
    body: str = ""


def parse_frontmatter(content: str) -> FrontmatterResult:
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return FrontmatterResult(body=content)

    end_index = -1
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break

    if end_index == -1:
        return FrontmatterResult(body=content)

    meta: dict[str, str] = {}
    for line in lines[1:end_index]:
        colon_index = line.find(":")
        if colon_index == -1:
            continue

        key = line[:colon_index].strip()
        value = line[colon_index + 1:].strip()
        if key:
            meta[key] = value

    body = "\n".join(lines[end_index + 1:]).strip()
    return FrontmatterResult(meta=meta, body=body)


def format_frontmatter(meta: dict[str, str], body: str) -> str:
    lines = ["---"]
    for key, value in meta.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    return "\n".join(lines)
