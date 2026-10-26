import discord
from discord import app_commands
from discord.ext import commands

from database.database import Database


class GifsCog(commands.Cog):

    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database

    # =====================================================
    # AUTOCOMPLETE
    # =====================================================

    async def gif_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:

        gifs = await self.database.get_gifs()

        current = current.lower()

        return [
            app_commands.Choice(name=name, value=name)
            for name, _ in gifs
            if current in name.lower()
        ][:25]

    # =====================================================
    # /GIF
    # =====================================================

    @app_commands.command(name="gif", description="Envoie un GIF enregistré.")
    @app_commands.describe(name="Nom du GIF")
    @app_commands.autocomplete(name=gif_autocomplete)
    async def gif(self, interaction: discord.Interaction, name: str) -> None:

        gifs = await self.database.get_gifs()

        gif = next(
            (
                (gif_name, url)
                for gif_name, url in gifs
                if gif_name.lower() == name.lower()
            ),
            None,
        )

        if gif is None:
            await interaction.response.send_message(
                f"❌ Le GIF `{name}` n'existe pas.", ephemeral=True
            )
            return

        _, url = gif

        await interaction.response.send_message(url)

    # =====================================================
    # /ADD-GIF
    # =====================================================

    @app_commands.command(name="add-gif", description="Ajoute un GIF.")
    @app_commands.describe(name="Nom du GIF", url="URL du GIF")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_gif(
        self, interaction: discord.Interaction, name: str, url: str
    ) -> None:

        name = name.strip()
        url = url.strip()

        if not name:
            await interaction.response.send_message(
                "❌ Le nom ne peut pas être vide.", ephemeral=True
            )
            return

        if not (url.startswith("http://") or url.startswith("https://")):
            await interaction.response.send_message(
                "❌ L'URL doit commencer par " "`http://` ou `https://`.",
                ephemeral=True,
            )
            return

        added = await self.database.add_gif(name, url)

        if not added:
            await interaction.response.send_message(
                f"❌ Le GIF `{name}` existe déjà.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ GIF `{name}` ajouté.", ephemeral=True
        )

    # =====================================================
    # /UPDATE-GIF
    # =====================================================

    @app_commands.command(name="update-gif", description="Modifie un GIF.")
    @app_commands.describe(name="Nom du GIF", url="Nouvelle URL")
    @app_commands.autocomplete(name=gif_autocomplete)
    @app_commands.checks.has_permissions(administrator=True)
    async def update_gif(
        self, interaction: discord.Interaction, name: str, url: str
    ) -> None:

        url = url.strip()

        if not (url.startswith("http://") or url.startswith("https://")):
            await interaction.response.send_message("❌ URL invalide.", ephemeral=True)
            return

        updated = await self.database.update_gif(name, url)

        if not updated:
            await interaction.response.send_message(
                f"❌ Le GIF `{name}` n'existe pas.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ GIF `{name}` modifié.", ephemeral=True
        )

    # =====================================================
    # /DELETE-GIF
    # =====================================================

    @app_commands.command(name="delete-gif", description="Supprime un GIF.")
    @app_commands.describe(name="Nom du GIF à supprimer")
    @app_commands.autocomplete(name=gif_autocomplete)
    @app_commands.checks.has_permissions(administrator=True)
    async def delete_gif(self, interaction: discord.Interaction, name: str) -> None:

        deleted = await self.database.delete_gif(name)

        if not deleted:
            await interaction.response.send_message(
                f"❌ Le GIF `{name}` n'existe pas.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"🗑️ GIF `{name}` supprimé.", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(GifsCog(bot, bot.database))
