import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import has_required_role


class RolesCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="roles", description="Affiche les rôles d'un utilisateur."
    )
    @app_commands.describe(user="Utilisateur dont tu veux afficher les rôles")
    @has_required_role()
    async def roles(
        self, interaction: discord.Interaction, user: discord.Member | None = None
    ) -> None:

        member = user or interaction.user

        roles = [
            role
            for role in reversed(member.roles)
            if role != interaction.guild.default_role
        ]

        if not roles:
            await interaction.response.send_message(
                f"❌ **{member.display_name}** n'a aucun rôle.", ephemeral=True
            )
            return

        roles_text = "\n".join(f"• {role.mention}" for role in roles)

        embed = discord.Embed(
            title=f"🎭 Roles — {member.display_name}",
            description=roles_text,
            color=member.color,
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        embed.set_footer(text=f"{len(roles)} rôle(s)")

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(RolesCog(bot))
