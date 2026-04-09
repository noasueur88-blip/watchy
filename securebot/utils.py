from __future__ import annotations

from datetime import datetime, timedelta, timezone

import discord

from securebot.storage import read_guild_state, write_guild_state


def create_embed(title: str, description: str, color: int = 0xD32F2F) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    embed.timestamp = datetime.now(timezone.utc)
    return embed


async def send_mod_log(guild: discord.Guild, channel_id: int | None, embed: discord.Embed) -> None:
    if not channel_id:
        return

    try:
        channel = guild.get_channel(channel_id) or await guild.fetch_channel(channel_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return

    if hasattr(channel, "send"):
        await channel.send(embed=embed)


def member_target_error(
    actor: discord.Member,
    target: discord.Member | None,
    bot_member: discord.Member,
    owner_id: int,
) -> str | None:
    if target is None:
        return "Membre introuvable sur ce serveur."
    if target.id == actor.id:
        return "Action refusee sur toi-meme."
    if target.id == owner_id:
        return "Le proprietaire du serveur ne peut pas etre cible."
    if actor.top_role <= target.top_role:
        return "Tu dois avoir un role plus haut que la cible."
    if bot_member.top_role <= target.top_role:
        return "Le bot n a pas une hierarchie suffisante pour agir."
    return None


async def set_channel_locked(channel: discord.abc.GuildChannel, locked: bool) -> bool:
    if not isinstance(channel, discord.TextChannel):
        return False

    overwrite = channel.overwrites_for(channel.guild.default_role)
    already_locked = overwrite.send_messages is False

    if locked == already_locked:
        return False

    overwrite.send_messages = False if locked else None
    await channel.set_permissions(channel.guild.default_role, overwrite=overwrite)
    return True


async def set_guild_maintenance(
    guild: discord.Guild,
    enabled: bool,
    reason: str,
    announce_channel: discord.abc.GuildChannel | None,
    bypass_role_ids: list[int],
    default_announce_channel_id: int | None,
) -> tuple[int, dict]:
    state = read_guild_state(guild.id)
    locked_channels: list[int] = []

    if enabled:
        for channel in guild.channels:
            if not isinstance(channel, discord.TextChannel):
                continue

            changed = await set_channel_locked(channel, True)
            if not changed:
                continue

            for role_id in bypass_role_ids:
                role = guild.get_role(role_id)
                if role is None:
                    continue
                overwrite = channel.overwrites_for(role)
                overwrite.send_messages = True
                await channel.set_permissions(role, overwrite=overwrite)

            locked_channels.append(channel.id)

        new_state = {
            "maintenance_enabled": True,
            "reason": reason,
            "announce_channel_id": announce_channel.id if announce_channel else default_announce_channel_id,
            "locked_channels": locked_channels,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        write_guild_state(guild.id, new_state)
        return len(locked_channels), new_state

    for channel_id in state.get("locked_channels", []):
        channel = guild.get_channel(channel_id)
        if channel is None:
            continue
        await set_channel_locked(channel, False)

    new_state = {
        "maintenance_enabled": False,
        "reason": None,
        "announce_channel_id": announce_channel.id if announce_channel else state.get("announce_channel_id", default_announce_channel_id),
        "locked_channels": [],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_guild_state(guild.id, new_state)
    return len(state.get("locked_channels", [])), new_state


def timeout_until(minutes: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)
