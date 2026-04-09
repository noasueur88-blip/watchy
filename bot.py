from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


DATA_DIR = Path.cwd() / "data"
SETTINGS_FILE = DATA_DIR / "guild-settings.json"


@dataclass(frozen=True)
class Settings:
    token: str
    guild_id: int | None
    mod_log_channel_id: int | None
    maintenance_announce_channel_id: int | None
    security_bypass_role_ids: list[int]


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


def optional_int(name: str) -> int | None:
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
        guild_id=optional_int("GUILD_ID"),
        mod_log_channel_id=optional_int("MOD_LOG_CHANNEL_ID"),
        maintenance_announce_channel_id=optional_int("MAINTENANCE_ANNOUNCE_CHANNEL_ID"),
        security_bypass_role_ids=security_bypass_role_ids,
    )


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
    announce_channel: discord.TextChannel | None,
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


class SecureBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.guild_messages = True
        intents.message_content = True
        intents.moderation = True
        intents.members = True

        super().__init__(command_prefix="!", intents=intents)
        self.settings = settings

    async def setup_hook(self) -> None:
        if self.settings.guild_id:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    def sync_app_commands(self) -> None:
        async def runner() -> None:
            async with self:
                await self.login(self.settings.token)
                if self.settings.guild_id:
                    guild = discord.Object(id=self.settings.guild_id)
                    synced = await self.tree.sync(guild=guild)
                else:
                    synced = await self.tree.sync()
                print(f"{len(synced)} slash command(s) synchronisee(s).")
                await self.close()

        asyncio.run(runner())


def create_bot() -> SecureBot:
    settings = load_settings()
    bot = SecureBot(settings)
    register_commands(bot)
    return bot


def register_commands(bot: SecureBot) -> None:
    @bot.event
    async def on_ready() -> None:
        if bot.user:
            print(f"{bot.user} est en ligne.")

    @bot.tree.command(name="ban", description="Bannit un membre du serveur")
    @app_commands.default_permissions(ban_members=True)
    async def ban(interaction: discord.Interaction, target: discord.Member, reason: str | None = None) -> None:
        await interaction.response.defer(ephemeral=True)
        actor = interaction.user
        assert isinstance(actor, discord.Member)
        assert interaction.guild is not None
        bot_member = interaction.guild.me or interaction.guild.get_member(bot.user.id if bot.user else 0)
        assert bot_member is not None

        error = member_target_error(actor, target, bot_member, interaction.guild.owner_id)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        final_reason = reason or "Aucune raison fournie"
        await target.ban(reason=f"{final_reason} | Par {interaction.user}")
        embed = create_embed("Ban execute", f"{target} a ete banni.\nRaison: {final_reason}")
        await interaction.followup.send(embed=embed, ephemeral=True)
        await send_mod_log(interaction.guild, bot.settings.mod_log_channel_id, embed)

    @bot.tree.command(name="kick", description="Expulse un membre du serveur")
    @app_commands.default_permissions(kick_members=True)
    async def kick(interaction: discord.Interaction, target: discord.Member, reason: str | None = None) -> None:
        await interaction.response.defer(ephemeral=True)
        actor = interaction.user
        assert isinstance(actor, discord.Member)
        assert interaction.guild is not None
        bot_member = interaction.guild.me or interaction.guild.get_member(bot.user.id if bot.user else 0)
        assert bot_member is not None

        error = member_target_error(actor, target, bot_member, interaction.guild.owner_id)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        final_reason = reason or "Aucune raison fournie"
        await target.kick(reason=f"{final_reason} | Par {interaction.user}")
        embed = create_embed("Kick execute", f"{target} a ete expulse.\nRaison: {final_reason}", 0xEF6C00)
        await interaction.followup.send(embed=embed, ephemeral=True)
        await send_mod_log(interaction.guild, bot.settings.mod_log_channel_id, embed)

    @bot.tree.command(name="timeout", description="Mute temporairement un membre")
    @app_commands.default_permissions(moderate_members=True)
    async def timeout(
        interaction: discord.Interaction,
        target: discord.Member,
        minutes: app_commands.Range[int, 1, 40320],
        reason: str | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        actor = interaction.user
        assert isinstance(actor, discord.Member)
        assert interaction.guild is not None
        bot_member = interaction.guild.me or interaction.guild.get_member(bot.user.id if bot.user else 0)
        assert bot_member is not None

        error = member_target_error(actor, target, bot_member, interaction.guild.owner_id)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        final_reason = reason or "Aucune raison fournie"
        await target.edit(timed_out_until=timeout_until(minutes), reason=f"{final_reason} | Par {interaction.user}")
        embed = create_embed("Timeout applique", f"{target} est mute pour {minutes} minute(s).\nRaison: {final_reason}", 0xF9A825)
        await interaction.followup.send(embed=embed, ephemeral=True)
        await send_mod_log(interaction.guild, bot.settings.mod_log_channel_id, embed)

    @bot.tree.command(name="untimeout", description="Retire le timeout d un membre")
    @app_commands.default_permissions(moderate_members=True)
    async def untimeout(interaction: discord.Interaction, target: discord.Member, reason: str | None = None) -> None:
        await interaction.response.defer(ephemeral=True)
        actor = interaction.user
        assert isinstance(actor, discord.Member)
        assert interaction.guild is not None
        bot_member = interaction.guild.me or interaction.guild.get_member(bot.user.id if bot.user else 0)
        assert bot_member is not None

        error = member_target_error(actor, target, bot_member, interaction.guild.owner_id)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        final_reason = reason or "Aucune raison fournie"
        await target.edit(timed_out_until=None, reason=f"{final_reason} | Par {interaction.user}")
        embed = create_embed("Timeout retire", f"{target} n est plus sanctionne.\nRaison: {final_reason}", 0x2E7D32)
        await interaction.followup.send(embed=embed, ephemeral=True)
        await send_mod_log(interaction.guild, bot.settings.mod_log_channel_id, embed)

    @bot.tree.command(name="purge", description="Supprime rapidement des messages")
    @app_commands.default_permissions(manage_messages=True)
    async def purge(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("Cette commande doit etre utilisee dans un salon texte.", ephemeral=True)
            return

        deleted = await channel.purge(limit=amount)
        embed = create_embed("Purge executee", f"{len(deleted)} message(s) supprime(s).", 0x1976D2)
        await interaction.followup.send(embed=embed, ephemeral=True)
        assert interaction.guild is not None
        await send_mod_log(interaction.guild, bot.settings.mod_log_channel_id, embed)

    @bot.tree.command(name="lock", description="Verrouille le salon actuel")
    @app_commands.default_permissions(manage_channels=True)
    async def lock(interaction: discord.Interaction, reason: str | None = None) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("Salon incompatible avec le verrouillage.", ephemeral=True)
            return

        final_reason = reason or "Aucune raison fournie"
        await set_channel_locked(channel, True)
        embed = create_embed("Salon verrouille", f"{channel.mention} est maintenant verrouille.\nRaison: {final_reason}", 0x455A64)
        await interaction.followup.send(embed=embed, ephemeral=True)
        assert interaction.guild is not None
        await send_mod_log(interaction.guild, bot.settings.mod_log_channel_id, embed)

    @bot.tree.command(name="unlock", description="Deverrouille le salon actuel")
    @app_commands.default_permissions(manage_channels=True)
    async def unlock(interaction: discord.Interaction, reason: str | None = None) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("Salon incompatible avec le deverrouillage.", ephemeral=True)
            return

        final_reason = reason or "Aucune raison fournie"
        await set_channel_locked(channel, False)
        embed = create_embed("Salon deverrouille", f"{channel.mention} est de nouveau ouvert.\nRaison: {final_reason}", 0x2E7D32)
        await interaction.followup.send(embed=embed, ephemeral=True)
        assert interaction.guild is not None
        await send_mod_log(interaction.guild, bot.settings.mod_log_channel_id, embed)

    @bot.tree.command(name="maintenance", description="Active ou desactive la maintenance du serveur")
    @app_commands.default_permissions(administrator=True)
    async def maintenance(
        interaction: discord.Interaction,
        enabled: bool,
        reason: str | None = None,
        announce_channel: discord.TextChannel | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        assert interaction.guild is not None

        final_reason = reason or "Maintenance planifiee"
        changed_channels, state = await set_guild_maintenance(
            guild=interaction.guild,
            enabled=enabled,
            reason=final_reason,
            announce_channel=announce_channel,
            bypass_role_ids=bot.settings.security_bypass_role_ids,
            default_announce_channel_id=bot.settings.maintenance_announce_channel_id,
        )

        label = "activee" if enabled else "desactivee"
        embed = create_embed(
            f"Maintenance {label}",
            f"Etat du serveur: {label}\nSalons modifies: {changed_channels}\nRaison: {final_reason}",
            0xC62828 if enabled else 0x2E7D32,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        await send_mod_log(interaction.guild, bot.settings.mod_log_channel_id, embed)

        target_channel_id = state.get("announce_channel_id")
        if target_channel_id:
            channel = interaction.guild.get_channel(target_channel_id)
            if isinstance(channel, discord.TextChannel):
                public_embed = create_embed(
                    "Serveur en maintenance" if enabled else "Maintenance terminee",
                    f"Le serveur est temporairement restreint.\nRaison: {final_reason}" if enabled else "Le serveur est de nouveau disponible.",
                    0xB71C1C if enabled else 0x1B5E20,
                )
                await channel.send(embed=public_embed)

    @bot.tree.command(name="security-status", description="Affiche l etat de securite du serveur")
    @app_commands.default_permissions(moderate_members=True)
    async def security_status(interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        state = read_guild_state(interaction.guild.id)
        bypass_roles = [
            interaction.guild.get_role(role_id).mention
            for role_id in bot.settings.security_bypass_role_ids
            if interaction.guild.get_role(role_id)
        ]
        embed = create_embed(
            "Etat securite",
            "\n".join(
                [
                    f"Maintenance: {'ACTIVE' if state.get('maintenance_enabled') else 'INACTIVE'}",
                    f"Salons verrouilles: {len(state.get('locked_channels', []))}",
                    f"Canal annonce: <#{state['announce_channel_id']}>" if state.get("announce_channel_id") else "Canal annonce: Non defini",
                    f"Roles bypass: {', '.join(bypass_roles) if bypass_roles else 'Aucun'}",
                ]
            ),
            0x1565C0,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


def main() -> None:
    bot = create_bot()
    bot.run(bot.settings.token)


if __name__ == "__main__":
    main()
