from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .frontmatter import parse_frontmatter


@dataclass
class SkillDefinition:
    name: str
    description: str
    when_to_use: str | None = None
    allowed_tools: list[str] | None = None
    user_invocable: bool = True
    context: str = "inline"
    prompt_template: str = ""
    source: str = "project"
    skill_dir: str = ""


_cached_skills: list[SkillDefinition] | None = None


def discover_skills() -> list[SkillDefinition]:
    global _cached_skills
    if _cached_skills is not None:
        return _cached_skills

    skills: dict[str, SkillDefinition] = {}
    _load_skills_from_dir(Path.home() / ".claude" / "skills", "user", skills)
    _load_skills_from_dir(Path.cwd() / ".claude" / "skills", "project", skills)

    _cached_skills = list(skills.values())
    return _cached_skills


def _load_skills_from_dir(
    base_dir: Path,
    source: str,
    skills: dict[str, SkillDefinition],
) -> None:
    if not base_dir.is_dir():
        return

    for entry in sorted(base_dir.iterdir()):
        if not entry.is_dir():
            continue
        skill_file = entry / "SKILL.md"
        if not skill_file.is_file():
            continue

        skill = _parse_skill_file(skill_file, source, str(entry))
        if skill:
            skills[skill.name] = skill


def _parse_skill_file(file_path: Path, source: str, skill_dir: str) -> SkillDefinition | None:
    try:
        parsed = parse_frontmatter(file_path.read_text(encoding="utf-8"))
    except OSError:
        return None

    meta = parsed.meta
    name = meta.get("name") or file_path.parent.name
    context = "fork" if meta.get("context") == "fork" else "inline"
    return SkillDefinition(
        name=name,
        description=meta.get("description", ""),
        when_to_use=meta.get("when_to_use") or meta.get("when-to-use"),
        allowed_tools=_parse_allowed_tools(meta.get("allowed-tools")),
        user_invocable=meta.get("user-invocable", "true") != "false",
        context=context,
        prompt_template=parsed.body,
        source=source,
        skill_dir=skill_dir,
    )


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


def get_skill_by_name(name: str) -> SkillDefinition | None:
    for skill in discover_skills():
        if skill.name == name:
            return skill
    return None


def resolve_skill_prompt(skill: SkillDefinition, args: str) -> str:
    prompt = skill.prompt_template
    prompt = re.sub(r"\$ARGUMENTS|\$\{ARGUMENTS\}", args, prompt)
    prompt = prompt.replace("${CLAUDE_SKILL_DIR}", skill.skill_dir)
    return prompt


def execute_skill(skill_name: str, args: str) -> dict | None:
    skill = get_skill_by_name(skill_name)
    if not skill:
        return None
    return {
        "prompt": resolve_skill_prompt(skill, args),
        "allowed_tools": skill.allowed_tools,
        "context": skill.context,
    }


def build_skill_descriptions() -> str:
    skills = discover_skills()
    if not skills:
        return ""

    lines = ["# Available Skills", ""]
    user_invocable = [skill for skill in skills if skill.user_invocable]
    auto_only = [skill for skill in skills if not skill.user_invocable]

    if user_invocable:
        lines.append("User-invocable skills:")
        for skill in user_invocable:
            lines.append(f"- /{skill.name}: {skill.description}")
            if skill.when_to_use:
                lines.append(f"  When to use: {skill.when_to_use}")
        lines.append("")

    if auto_only:
        lines.append("Auto-invocable skills:")
        for skill in auto_only:
            lines.append(f"- {skill.name}: {skill.description}")
            if skill.when_to_use:
                lines.append(f"  When to use: {skill.when_to_use}")

    return "\n".join(lines).rstrip()


def reset_skill_cache() -> None:
    global _cached_skills
    _cached_skills = None
