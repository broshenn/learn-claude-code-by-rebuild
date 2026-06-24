from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SESSION_DIR = Path.home() / ".mini-claude-rebuild" / "sessions"


def _ensure_dir() -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)


def save_session(session_id: str, data: dict[str, Any]) -> None:
    _ensure_dir()
    path = SESSION_DIR / f"{session_id}.json"
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def load_session(session_id: str) -> dict[str, Any] | None:
    path = SESSION_DIR / f"{session_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_sessions() -> list[dict[str, Any]]:
    _ensure_dir()
    sessions: list[dict[str, Any]] = []
    for path in SESSION_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        metadata = data.get("metadata")
        if isinstance(metadata, dict):
            sessions.append(metadata)
    return sessions


def get_latest_session_id() -> str | None:
    sessions = list_sessions()
    if not sessions:
        return None
    sessions.sort(key=lambda item: item.get("startTime", ""), reverse=True)
    latest_id = sessions[0].get("id")
    return latest_id if isinstance(latest_id, str) else None
