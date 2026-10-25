from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

import config

from database.database import Database
from services.image_service import ImageService


class XPCog(commands.Cog):

    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database

        self.image_service = ImageService()

    # =====================================================
    # /RANK
    # =====================================================

    @app_commands.command(
        name="rank", description="Affiche le rang et l'XP d'un utilisateur."
    )
    @app_commands.describe(user="L'utilisateur dont tu veux voir le rang")
    async def rank(
        self, interaction: discord.Interaction, user: discord.Member | None = None
    ) -> None:

        await interaction.response.defer()

        selected_user = user or interaction.user

        if interaction.guild is None:
            await interaction.followup.send(
                "Cette commande doit être utilisée dans un serveur.", ephemeral=True
            )
            return

        target = interaction.guild.get_member(selected_user.id)

        if target is None:
            await interaction.followup.send(
                "Impossible de récupérer ce membre.", ephemeral=True
            )
            return

        print(f"STATUS DEBUG | " f"{target.display_name} = {target.status}")

        xp = await self.database.get_user_xp(target.id)

        level = await self.database.get_user_level(target.id)

        rank = await self.database.get_user_rank(target.id)

        _, current_xp, next_level_xp, _ = self.database.get_xp_stats(xp, level)

        image_path: Path | None = None

        try:
            print(f"STATUS DEBUG | " f"{target.display_name} = {target.status}")
            image_path = await self.image_service.generate_rank_card(
                user=target,
                display_name=target.display_name,
                status=target.status,
                level=level,
                rank=rank,
                current_xp=current_xp,
                next_level_xp=next_level_xp,
            )

            await interaction.followup.send(
                file=discord.File(image_path, filename="rank.png")
            )

        except Exception as error:

            print(f"❌ Erreur /rank : {error}")

            await interaction.followup.send(
                "Une erreur est survenue pendant " "la génération de la carte de rang.",
                ephemeral=True,
            )

        finally:

            if image_path is not None and image_path.exists():
                image_path.unlink()

    @app_commands.command(name="add-xp", description="Ajoute de l'XP à un utilisateur.")
    @app_commands.describe(
        user="Utilisateur auquel ajouter de l'XP", amount="Quantité d'XP à ajouter"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def add_xp(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1, 1_000_000],
    ) -> None:

        await interaction.response.defer(ephemeral=True)

        old_xp = await self.database.get_user_xp(user.id)

        old_level = await self.database.get_user_level(user.id)

        leveled_up, new_level, new_xp = await self.database.add_xp(
            user.id, user.display_name, amount
        )

        embed = discord.Embed(title="⭐ XP ajouté", color=discord.Color.green())

        embed.set_thumbnail(url=user.display_avatar.url)

        embed.add_field(name="Utilisateur", value=user.mention, inline=False)

        embed.add_field(name="XP", value=f"{old_xp:,} → **{new_xp:,}**", inline=True)

        embed.add_field(name="Ajout", value=f"+{amount:,} XP", inline=True)

        embed.add_field(
            name="Niveau", value=f"{old_level} → **{new_level}**", inline=True
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

        if leveled_up:
            await self.bot.xp_service.send_level_up(user, new_level, new_xp)

    @app_commands.command(
        name="update-xp", description="Définit l'XP total d'un utilisateur."
    )
    @app_commands.describe(
        user="Utilisateur à modifier", xp="Nouvelle quantité totale d'XP"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def update_xp(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        xp: app_commands.Range[int, 0, 1_000_000],
    ) -> None:

        await interaction.response.defer(ephemeral=True)

        old_xp = await self.database.get_user_xp(user.id)

        old_level = await self.database.get_user_level(user.id)

        new_xp, new_level = await self.database.set_user_xp(
            user.id, user.display_name, xp
        )

        embed = discord.Embed(title="🛠️ XP modifié", color=discord.Color.orange())

        embed.set_thumbnail(url=user.display_avatar.url)

        embed.add_field(name="Utilisateur", value=user.mention, inline=False)

        embed.add_field(
            name="XP", value=(f"{old_xp:,} → " f"**{new_xp:,}**"), inline=True
        )

        embed.add_field(
            name="Niveau", value=(f"{old_level} → " f"**{new_level}**"), inline=True
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="leaderboard", description="Affiche le classement XP du serveur."
    )
    async def leaderboard(self, interaction: discord.Interaction) -> None:

        await interaction.response.defer()

        leaderboard = await self.database.get_leaderboard()

        if not leaderboard:
            await interaction.followup.send("Le classement XP est vide.")
            return

        if interaction.guild is None:
            await interaction.followup.send(
                "Cette commande doit être utilisée " "dans un serveur.", ephemeral=True
            )
            return

        lines = []

        position = 0

        for user_id, username, level, xp in leaderboard:

            # On évite d'afficher les utilisateurs
            # qui ne sont plus sur le serveur.
            member = interaction.guild.get_member(user_id)

            if member is None:
                continue

            if member.bot:
                continue

            position += 1

            if position == 1:
                medal = "🥇"
            elif position == 2:
                medal = "🥈"
            elif position == 3:
                medal = "🥉"
            else:
                medal = f"`#{position}`"

            lines.append(
                f"{medal} **{member.display_name}**\n"
                f"└ Niveau **{level}** • "
                f"{xp:,} XP"
            )

            if position >= 10:
                break

        if not lines:
            await interaction.followup.send("Aucun utilisateur à afficher.")
            return

        embed = discord.Embed(
            title="🏆 Leaderboard",
            description="\n\n".join(lines),
            color=discord.Color.gold(),
        )

        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        embed.set_footer(text=f"{interaction.guild.name} • Top 10")

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(XPCog(bot, bot.database))
