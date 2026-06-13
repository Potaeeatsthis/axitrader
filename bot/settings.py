"""Persistent settings — small key-value store alongside holdings.json."""
import json
import os
from pathlib import Path
from typing import Any

SETTINGS_FILE = Path(os.environ.get("SETTINGS_FILE", "/data/settings.json"))

# Friendly aliases → real model IDs.
# Update these when Anthropic ships new models.
MODEL_ALIASES = {
    "opus":   "claude-opus-4-8",
    "sonnet": "claude-sonnet-4-6",
    "haiku":  "claude-haiku-4-5-20251001",
}

# All model IDs the bot will accept verbatim (so power users can pin a specific version).
KNOWN_MODELS = {
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
}


def _load() -> dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except Exception:
        return {}


def _save(data: dict[str, Any]) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, indent=2))


def get_setting(key: str, default: Any = None) -> Any:
    return _load().get(key, default)


def set_setting(key: str, value: Any) -> None:
    data = _load()
    data[key] = value
    _save(data)


# ─── Model helpers ───────────────────────────────────────────────────────────

def resolve_model(name: str) -> str | None:
    """Map an alias or full ID to a real model ID. Returns None if unknown."""
    name = name.strip().lower()
    if name in MODEL_ALIASES:
        return MODEL_ALIASES[name]
    if name in KNOWN_MODELS:
        return name
    return None


def get_model() -> str:
    """Active model: persisted setting → env default → sonnet fallback."""
    return (
        get_setting("model")
        or os.environ.get("CLAUDE_MODEL")
        or "claude-sonnet-4-6"
    )


def set_model(name: str) -> str:
    """Persist a new active model. Returns the resolved ID. Raises ValueError if unknown."""
    resolved = resolve_model(name)
    if not resolved:
        raise ValueError(f"Unknown model: {name}")
    set_setting("model", resolved)
    return resolved
