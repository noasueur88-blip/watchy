from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from securebot.config import Settings, load_settings
from securebot.storage import read_guild_state
from securebot.utils import (
    create_embed,
    member_target_error,
    send_mod_log,
    set_channel_locked,
    set_guild_maintenance,
    timeout_until,
)


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
    async def ban(
        interaction: discord.Interaction,
        target: discord.Member,
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
        await target.ban(reason=f"{final_reason} | Par {interaction.user}")
        embed = create_embed("Ban execute", f"{target} a ete banni.\nRaison: {final_reason}")
        await interaction.followup.send(embed=embed, ephemeral=True)
        await send_mod_log(interaction.guild, bot.settings.mod_log_channel_id, embed)

    @bot.tree.command(name="kick", description="Expulse un membre du serveur")
    @app_commands.default_permissions(kick_members=True)
    async def kick(
        interaction: discord.Interaction,
        target: discord.Member,
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
        embed = create_embed(
            "Timeout applique",
            f"{target} est mute pour {minutes} minute(s).\nRaison: {final_reason}",
            0xF9A825,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        await send_mod_log(interaction.guild, bot.settings.mod_log_channel_id, embed)

    @bot.tree.command(name="untimeout", description="Retire le timeout d un membre")
    @app_commands.default_permissions(moderate_members=True)
    async def untimeout(
        interaction: discord.Interaction,
        target: discord.Member,
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
        await target.edit(timed_out_until=None, reason=f"{final_reason} | Par {interaction.user}")
        embed = create_embed("Timeout retire", f"{target} n est plus sanctionne.\nRaison: {final_reason}", 0x2E7D32)
        await interaction.followup.send(embed=embed, ephemeral=True)
        await send_mod_log(interaction.guild, bot.settings.mod_log_channel_id, embed)

    @bot.tree.command(name="purge", description="Supprime rapidement des messages")
    @app_commands.default_permissions(manage_messages=True)
    async def purge(
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100],
    ) -> None:
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
    async def lock(
        interaction: discord.Interaction,
        reason: str | None = None,
    ) -> None:
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
    async def unlock(
        interaction: discord.Interaction,
        reason: str | None = None,
    ) -> None:
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
                    f"Le serveur est temporairement restreint.\nRaison: {final_reason}"
                    if enabled else "Le serveur est de nouveau disponible.",
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
