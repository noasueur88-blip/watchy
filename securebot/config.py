from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    token: str
    guild_id: int | None
    mod_log_channel_id: int | None
    maintenance_announce_channel_id: int | None
    security_bypass_role_ids: list[int]


def _optional_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    return int(value) if value else None


def load_settings() -> Settings:
    load_dotenv()

    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError("DISCORD_TOKEN est obligatoire.")

    raw_roles = os.getenv("SECURITY_BYPASS_ROLE_IDS", "")
    security_bypass_role_ids = [int(value.strip()) for value in raw_roles.split(",") if value.strip()]

    return Settings(
        token=token,
        guild_id=_optional_int("GUILD_ID"),
        mod_log_channel_id=_optional_int("MOD_LOG_CHANNEL_ID"),
        maintenance_announce_channel_id=_optional_int("MAINTENANCE_ANNOUNCE_CHANNEL_ID"),
        security_bypass_role_ids=security_bypass_role_ids,
    )
