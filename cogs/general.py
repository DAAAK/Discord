import discord
from discord import app_commands
from discord.ext import commands

import config

from database.database import Database
from utils.checks import (
    WrongChannel,
    MissingRequiredRole,
    has_required_role,
    channel_only,
)


class GeneralCog(commands.Cog):

    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database

    # =====================================================
    # AUTOCOMPLETE COMMAND
    # =====================================================

    async def command_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:

        commands_list = await self.database.get_all_commands()

        current = current.lower()

        return [
            app_commands.Choice(name=name, value=name)
            for name, _ in commands_list
            if current in name.lower()
        ][:25]

    async def refresh_help_message(self) -> None:

        channel = self.bot.get_channel(config.COMMANDS_CHANNEL_ID)

        if channel is None:
            try:
                channel = await self.bot.fetch_channel(config.COMMANDS_CHANNEL_ID)
            except discord.HTTPException as error:
                print(f"❌ Impossible de récupérer " f"le salon Commands : {error}")
                return

        try:
            message = await channel.fetch_message(config.COMMANDS_MESSAGE_ID)

        except discord.NotFound:
            print("❌ Le message Help permanent " "n'existe plus.")
            return

        except discord.HTTPException as error:
            print(f"❌ Impossible de récupérer " f"le message Help : {error}")
            return

        commands_list = await self.database.get_all_commands()

        commands_list.sort(key=lambda item: item[0].lower())

        embed = discord.Embed(
            title="📖 Here are the commands you can use", color=discord.Color.green()
        )

        if not commands_list:

            embed.description = "*No commands registered.*"

        else:

            for name, description in commands_list:

                command_name = name if name.startswith("/") else f"/{name}"

                embed.add_field(name=command_name, value=description, inline=True)

        await message.edit(embed=embed)

    # =====================================================
    # /HELP
    # =====================================================

    @app_commands.command(name="help", description="Actualise la liste des commandes.")
    @channel_only(config.COMMANDS_CHANNEL_ID)
    async def help_command(self, interaction: discord.Interaction) -> None:

        await interaction.response.defer(ephemeral=True)

        await self.refresh_help_message()

        await interaction.followup.send(
            "✅ La liste des commandes a été actualisée.", ephemeral=True
        )

    # =====================================================
    # /ADD-CMD
    # =====================================================

    @app_commands.command(
        name="add-cmd", description="Ajoute une commande au menu Help."
    )
    @app_commands.describe(
        name="Nom de la commande", description="Description de la commande"
    )
    @has_required_role()
    @channel_only(config.COMMANDS_CHANNEL_ID)
    async def add_cmd(
        self, interaction: discord.Interaction, name: str, description: str
    ) -> None:

        name = name.strip().lstrip("/")
        description = description.strip()

        if not name:
            await interaction.response.send_message(
                "❌ Le nom ne peut pas être vide.", ephemeral=True
            )
            return

        if not description:
            await interaction.response.send_message(
                "❌ La description ne peut pas être vide.", ephemeral=True
            )
            return

        added = await self.database.add_command(name, description)

        if not added:
            await interaction.response.send_message(
                f"❌ La commande `/{name}` existe déjà.", ephemeral=True
            )
            return

        await self.refresh_help_message()

        await interaction.response.send_message(
            f"✅ `/{name}` a été ajoutée au Help.", ephemeral=True
        )

    # =====================================================
    # /UPDATE-CMD
    # =====================================================

    @app_commands.command(
        name="update-cmd", description="Modifie une commande du menu Help."
    )
    @app_commands.describe(
        name="Commande à modifier", description="Nouvelle description"
    )
    @app_commands.autocomplete(name=command_autocomplete)
    @has_required_role()
    @channel_only(config.COMMANDS_CHANNEL_ID)
    async def update_cmd(
        self, interaction: discord.Interaction, name: str, description: str
    ) -> None:

        name = name.strip().lstrip("/")
        description = description.strip()

        if not description:
            await interaction.response.send_message(
                "❌ La description ne peut pas être vide.", ephemeral=True
            )
            return

        updated = await self.database.update_command(name, description)

        if not updated:
            await interaction.response.send_message(
                f"❌ La commande `/{name}` n'existe pas.", ephemeral=True
            )
            return

        await self.refresh_help_message()

        await interaction.response.send_message(
            f"✅ `/{name}` a été mise à jour.", ephemeral=True
        )

    # =====================================================
    # /DELETE-CMD
    # =====================================================

    @app_commands.command(
        name="delete-cmd", description="Supprime une commande du menu Help."
    )
    @app_commands.describe(name="Commande à supprimer")
    @app_commands.autocomplete(name=command_autocomplete)
    @has_required_role()
    @channel_only(config.COMMANDS_CHANNEL_ID)
    async def delete_cmd(self, interaction: discord.Interaction, name: str) -> None:

        name = name.strip().lstrip("/")

        deleted = await self.database.delete_command(name)

        if not deleted:
            await interaction.response.send_message(
                f"❌ La commande `/{name}` n'existe pas.", ephemeral=True
            )
            return

        await self.refresh_help_message()

        await interaction.response.send_message(
            f"🗑️ `/{name}` a été supprimée du Help.", ephemeral=True
        )

    # =====================================================
    # ERRORS
    # =====================================================

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:

        if isinstance(error, WrongChannel):

            message = (
                "❌ Cette commande peut uniquement "
                f"être utilisée dans <#{error.channel_id}>."
            )

        elif isinstance(error, MissingRequiredRole):

            message = "❌ Tu n'as pas le rôle requis " "pour utiliser cette commande."

        else:

            print("❌ Erreur commande General : " f"{type(error).__name__}: {error}")

            message = (
                "❌ Une erreur est survenue pendant " "l'exécution de la commande."
            )

        if interaction.response.is_done():

            await interaction.followup.send(message, ephemeral=True)

        else:

            await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCog(bot, bot.database))
