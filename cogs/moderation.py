import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import (
    MissingRequiredRole,
    has_required_role,
)


class ModerationCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # =====================================================
    # /BAN
    # =====================================================

    @app_commands.command(name="ban", description="Bannit un utilisateur du serveur.")
    @app_commands.describe(user="Utilisateur à bannir", reason="Raison du bannissement")
    @has_required_role()
    async def ban(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str | None = None,
    ) -> None:

        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None:
            await interaction.followup.send(
                "❌ Cette commande doit être utilisée dans un serveur.", ephemeral=True
            )
            return

        if user.id == interaction.user.id:
            await interaction.followup.send(
                "❌ Tu ne peux pas te bannir toi-même.", ephemeral=True
            )
            return

        if user.id == self.bot.user.id:
            await interaction.followup.send(
                "❌ Tu ne peux pas bannir le bot.", ephemeral=True
            )
            return

        try:
            await user.ban(reason=reason or (f"Ban par {interaction.user}"))

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Je n'ai pas la permission de bannir "
                "cet utilisateur. Vérifie la hiérarchie des rôles.",
                ephemeral=True,
            )
            return

        except discord.HTTPException as error:
            print(f"❌ Erreur /ban : {error}")

            await interaction.followup.send(
                "❌ Impossible de bannir cet utilisateur.", ephemeral=True
            )
            return

        embed = discord.Embed(title="🔨 Utilisateur banni", color=discord.Color.red())

        embed.add_field(name="Utilisateur", value=f"{user} ({user.id})", inline=False)

        embed.add_field(name="Modérateur", value=interaction.user.mention, inline=False)

        embed.add_field(name="Raison", value=reason or "Aucune raison", inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    # =====================================================
    # /KICK
    # =====================================================

    @app_commands.command(name="kick", description="Expulse un utilisateur du serveur.")
    @app_commands.describe(
        user="Utilisateur à expulser", reason="Raison de l'expulsion"
    )
    @has_required_role()
    async def kick(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str | None = None,
    ) -> None:

        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None:
            await interaction.followup.send(
                "❌ Cette commande doit être utilisée dans un serveur.", ephemeral=True
            )
            return

        if user.id == interaction.user.id:
            await interaction.followup.send(
                "❌ Tu ne peux pas t'expulser toi-même.", ephemeral=True
            )
            return

        if self.bot.user and user.id == self.bot.user.id:
            await interaction.followup.send(
                "❌ Tu ne peux pas expulser le bot.", ephemeral=True
            )
            return

        try:

            await user.kick(reason=reason or (f"Kick par {interaction.user}"))

        except discord.Forbidden:

            await interaction.followup.send(
                "❌ Je n'ai pas la permission d'expulser "
                "cet utilisateur. Vérifie la hiérarchie des rôles.",
                ephemeral=True,
            )
            return

        except discord.HTTPException as error:

            print(f"❌ Erreur /kick : {error}")

            await interaction.followup.send(
                "❌ Impossible d'expulser cet utilisateur.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="👢 Utilisateur expulsé", color=discord.Color.orange()
        )

        embed.add_field(name="Utilisateur", value=f"{user} ({user.id})", inline=False)

        embed.add_field(name="Modérateur", value=interaction.user.mention, inline=False)

        embed.add_field(name="Raison", value=reason or "Aucune raison", inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    # =====================================================
    # /PURGE
    # =====================================================

    @app_commands.command(
        name="purge", description="Supprime plusieurs messages du salon."
    )
    @app_commands.describe(amount="Nombre de messages à supprimer")
    @has_required_role()
    async def purge(
        self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]
    ) -> None:

        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ Cette commande doit être utilisée " "dans un salon textuel.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            deleted = await channel.purge(limit=amount)

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Je n'ai pas la permission " "de supprimer les messages.",
                ephemeral=True,
            )
            return

        except discord.HTTPException as error:
            print(f"❌ Erreur /purge : {error}")

            await interaction.followup.send(
                "❌ Une erreur est survenue pendant " "la suppression.", ephemeral=True
            )
            return

        await interaction.followup.send(
            f"🧹 **{len(deleted)}** message(s) supprimé(s).", ephemeral=True
        )

    # =====================================================
    # ERRORS
    # =====================================================

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:

        if isinstance(error, MissingRequiredRole):
            message = "❌ Tu n'as pas le rôle requis " "pour utiliser cette commande."

        else:
            print("❌ Erreur Moderation : " f"{type(error).__name__}: {error}")

            message = (
                "❌ Une erreur est survenue pendant " "l'exécution de la commande."
            )

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
