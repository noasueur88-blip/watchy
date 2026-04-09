from __future__ import annotations

import json
from pathlib import Path


DATA_DIR = Path.cwd() / "data"
SETTINGS_FILE = DATA_DIR / "guild-settings.json"


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_FILE.exists():
        SETTINGS_FILE.write_text("{}", encoding="utf-8")


def read_guild_settings() -> dict[str, dict]:
    ensure_storage()
    return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))


def read_guild_state(guild_id: int) -> dict:
    settings = read_guild_settings()
    return settings.get(str(guild_id), {"maintenance_enabled": False, "locked_channels": []})


def write_guild_state(guild_id: int, next_state: dict) -> None:
    settings = read_guild_settings()
    settings[str(guild_id)] = next_state
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
