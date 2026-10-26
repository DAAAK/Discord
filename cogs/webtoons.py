from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

import config

from database.database import Database
from utils.checks import (
    WrongChannel,
    has_required_role,
    channel_only,
    MissingRequiredRole,
)


class WebtoonView(discord.ui.View):

    STATUS_ORDER = ["To Read", "On Going", "Up to Date", "Done"]

    STATUS_DISPLAY = {
        "To Read": "🔴 To Read",
        "On Going": "🟠 On Going",
        "Up to Date": "🟡 Up to Date",
        "Done": "🟢 Done",
    }

    def __init__(self, webtoons: list[tuple[str, int, str]]):
        super().__init__(timeout=None)

        self.webtoons = webtoons
        self.pages = self.build_pages()
        self.page = 0

        self.update_buttons()

    # =====================================================
    # BUILD PAGES
    # =====================================================

    def build_pages(self) -> list[tuple[str, list[tuple[str, int]]]]:

        pages = []

        # On garde une petite marge sous les 1024
        # caractères autorisés par Discord.
        MAX_CHARACTERS = 1000

        for status in self.STATUS_ORDER:

            entries = [
                (name, chapter)
                for name, chapter, webtoon_status in self.webtoons
                if webtoon_status == status
            ]

            entries.sort(key=lambda item: item[0].lower())

            if not entries:
                continue

            current_page = []
            current_length = 0

            for name, chapter in entries:

                line = f"**{name}** " f"(Chap. {chapter})\n"

                line_length = len(line)

                # Si ajouter ce webtoon dépasse la limite,
                # on termine la page actuelle.
                if current_page and current_length + line_length > MAX_CHARACTERS:

                    pages.append((status, current_page))

                    current_page = []
                    current_length = 0

                current_page.append((name, chapter))

                current_length += line_length

            # Dernière page de la catégorie
            if current_page:
                pages.append((status, current_page))

        return pages

    # =====================================================
    # COUNTS
    # =====================================================

    def get_counts(self) -> dict[str, int]:

        return {
            status: sum(
                1 for _, _, webtoon_status in self.webtoons if webtoon_status == status
            )
            for status in self.STATUS_ORDER
        }

    # =====================================================
    # EMBED
    # =====================================================

    def create_embed(self) -> discord.Embed:

        status, entries = self.pages[self.page]

        status_name = self.STATUS_DISPLAY.get(status, status)

        content = "\n".join(
            f"**{name}** (Chap. {chapter})" for name, chapter in entries
        )

        counts = self.get_counts()

        total = len(self.webtoons)

        embed = discord.Embed(title="📚 Webtoons", color=discord.Color.blue())

        embed.add_field(name=status_name, value=content, inline=False)

        summary = (
            f"Page {self.page + 1}/{len(self.pages)}\n"
            f"• Total: **{total}** webtoons\n"
            f"• 🔴 To Read: **{counts['To Read']}**\n"
            f"• 🟠 On Going: **{counts['On Going']}**\n"
            f"• 🟡 Up to Date: **{counts['Up to Date']}**\n"
            f"• 🟢 Done: **{counts['Done']}**\n"
            f"• 🕒 "
            f"{datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )

        embed.add_field(name="\u200b", value=summary, inline=False)

        return embed

    # =====================================================
    # BUTTONS
    # =====================================================

    def update_buttons(self) -> None:

        self.previous_button.disabled = self.page == 0

        self.next_button.disabled = self.page >= len(self.pages) - 1

    # =====================================================
    # PREVIOUS
    # =====================================================

    @discord.ui.button(
        label="← Previous",
        style=discord.ButtonStyle.primary,
        custom_id="webtoons:previous",
    )
    async def previous_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:

        if self.page > 0:
            self.page -= 1

        self.update_buttons()

        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    # =====================================================
    # NEXT
    # =====================================================

    @discord.ui.button(
        label="Next →", style=discord.ButtonStyle.primary, custom_id="webtoons:next"
    )
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:

        if self.page < len(self.pages) - 1:
            self.page += 1

        self.update_buttons()

        await interaction.response.edit_message(embed=self.create_embed(), view=self)


class WebtoonsCog(commands.Cog):

    STATUSES = ["To Read", "On Going", "Up to Date", "Done"]

    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database

        self.webtoon_view = None

    async def cog_load(self) -> None:

        webtoons = await self.database.get_all_webtoons()

        if not webtoons:
            return

        self.webtoon_view = WebtoonView(webtoons=webtoons)

        self.bot.add_view(self.webtoon_view, message_id=config.WEBTOON_MESSAGE_ID)

        print("📚 Vue Webtoons persistante enregistrée.")

    # =====================================================
    # REFRESH WEBTOON MESSAGE
    # =====================================================

    async def refresh_webtoon_message(self) -> None:

        channel = self.bot.get_channel(config.WEBTOON_CHANNEL_ID)

        if channel is None:
            try:
                channel = await self.bot.fetch_channel(config.WEBTOON_CHANNEL_ID)
            except discord.HTTPException as error:
                print(f"❌ Impossible de récupérer " f"le salon Webtoons : {error}")
                return

        try:
            message = await channel.fetch_message(config.WEBTOON_MESSAGE_ID)

        except discord.NotFound:
            print("❌ Le message Webtoons permanent " "n'existe plus.")
            return

        except discord.HTTPException as error:
            print(f"❌ Impossible de récupérer " f"le message Webtoons : {error}")
            return

        webtoons = await self.database.get_all_webtoons()

        if not webtoons:
            embed = discord.Embed(
                title="📚 Webtoons",
                description="*Aucun webtoon enregistré.*",
                color=discord.Color.blue(),
            )

            await message.edit(embed=embed, view=None)

            return

        self.webtoon_view = WebtoonView(webtoons=webtoons)

        await message.edit(
            embed=self.webtoon_view.create_embed(), view=self.webtoon_view
        )

    # =====================================================
    # AUTOCOMPLETE WEBTOON
    # =====================================================

    async def webtoon_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:

        webtoons = await self.database.get_all_webtoons()

        current = current.lower()

        return [
            app_commands.Choice(name=name, value=name)
            for name, _, _ in webtoons
            if current in name.lower()
        ][:25]

    # =====================================================
    # AUTOCOMPLETE STATUS
    # =====================================================

    async def status_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:

        current = current.lower()

        return [
            app_commands.Choice(name=status, value=status)
            for status in self.STATUSES
            if current in status.lower()
        ]

    # =====================================================
    # /WEBTOONS
    # =====================================================

    @app_commands.command(name="webtoons", description="Actualise le message Webtoons.")
    @has_required_role()
    @channel_only(config.WEBTOON_CHANNEL_ID)
    async def webtoons(self, interaction: discord.Interaction) -> None:

        await interaction.response.defer(ephemeral=True)

        await self.refresh_webtoon_message()

        await interaction.followup.send(
            "✅ Le message Webtoons a été actualisé.", ephemeral=True
        )

    # =====================================================
    # /ADD-WEBTOON
    # =====================================================

    @app_commands.command(name="add-webtoon", description="Ajoute un webtoon.")
    @app_commands.describe(
        name="Nom du webtoon", chapter="Chapitre actuel", status="Statut du webtoon"
    )
    @app_commands.autocomplete(status=status_autocomplete)
    @has_required_role()
    @channel_only(config.WEBTOON_CHANNEL_ID)
    async def add_webtoon(
        self,
        interaction: discord.Interaction,
        name: str,
        chapter: app_commands.Range[int, 0, 100000],
        status: str,
    ) -> None:

        name = name.strip()

        if status not in self.STATUSES:
            await interaction.response.send_message(
                "❌ Statut invalide. Utilise "
                "`To Read`, `On Going`, "
                "`Up to Date` ou `Done`.",
                ephemeral=True,
            )
            return

        added = await self.database.add_webtoon(name, chapter, status)

        if not added:
            await interaction.response.send_message(
                f"❌ `{name}` existe déjà.", ephemeral=True
            )
            return

        await self.refresh_webtoon_message()

        await interaction.response.send_message(
            f"✅ **{name}** ajouté — " f"chapitre `{chapter}` • `{status}`.",
            ephemeral=True,
        )

    # =====================================================
    # /UPDATE-WEBTOON
    # =====================================================

    @app_commands.command(name="update-webtoon", description="Modifie un webtoon.")
    @app_commands.describe(
        name="Webtoon à modifier", chapter="Nouveau chapitre", status="Nouveau statut"
    )
    @app_commands.autocomplete(name=webtoon_autocomplete, status=status_autocomplete)
    @has_required_role()
    @channel_only(config.WEBTOON_CHANNEL_ID)
    async def update_webtoon(
        self,
        interaction: discord.Interaction,
        name: str,
        chapter: app_commands.Range[int, 0, 100000],
        status: str,
    ) -> None:

        if status not in self.STATUSES:
            await interaction.response.send_message(
                "❌ Statut invalide.", ephemeral=True
            )
            return

        updated = await self.database.update_webtoon(name, chapter, status)

        if not updated:
            await interaction.response.send_message(
                f"❌ `{name}` n'existe pas.", ephemeral=True
            )
            return

        await self.refresh_webtoon_message()

        await interaction.response.send_message(
            f"✅ **{name}** mis à jour — " f"chapitre `{chapter}` • `{status}`.",
            ephemeral=True,
        )

    # =====================================================
    # /DELETE-WEBTOON
    # =====================================================

    @app_commands.command(name="delete-webtoon", description="Supprime un webtoon.")
    @app_commands.describe(name="Webtoon à supprimer")
    @app_commands.autocomplete(name=webtoon_autocomplete)
    @has_required_role()
    @channel_only(config.WEBTOON_CHANNEL_ID)
    async def delete_webtoon(self, interaction: discord.Interaction, name: str) -> None:

        deleted = await self.database.delete_webtoon(name)

        if not deleted:
            await interaction.response.send_message(
                f"❌ `{name}` n'existe pas.", ephemeral=True
            )
            return

        await self.refresh_webtoon_message()

        await interaction.response.send_message(
            f"🗑️ **{name}** supprimé.", ephemeral=True
        )

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
            print(f"❌ Erreur commande Webtoons : " f"{type(error).__name__}: {error}")

            message = (
                "❌ Une erreur est survenue pendant " "l'exécution de la commande."
            )

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(WebtoonsCog(bot, bot.database))
