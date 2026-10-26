import discord

from discord import app_commands
from discord.ext import commands, tasks

import config

from database.database import Database
from services.twitch_service import TwitchService

from utils.checks import (
    MissingRequiredRole,
    has_required_role,
)


class TwitchCog(commands.Cog):

    def __init__(
        self,
        bot: commands.Bot,
        database: Database,
        twitch_service: TwitchService,
    ):
        self.bot = bot
        self.database = database
        self.twitch_service = twitch_service

        self.check_streamers.start()

    # =====================================================
    # CLOSE
    # =====================================================

    def cog_unload(self) -> None:
        self.check_streamers.cancel()

    # =====================================================
    # AUTOCOMPLETE
    # =====================================================

    async def streamer_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:

        streamers = await self.database.get_all_streamers()

        choices = []

        for _, twitch_username, _ in streamers:

            if current.lower() not in twitch_username.lower():
                continue

            choices.append(
                app_commands.Choice(
                    name=twitch_username,
                    value=twitch_username,
                )
            )

            if len(choices) >= 25:
                break

        return choices

    # =====================================================
    # /STREAMERS
    # =====================================================

    @app_commands.command(
        name="streamers", description="Affiche les streamers enregistrés."
    )
    async def streamers(
        self,
        interaction: discord.Interaction,
    ) -> None:

        await interaction.response.defer()

        streamers = await self.database.get_all_streamers()

        if not streamers:

            await interaction.followup.send("🟣 Aucun streamer enregistré.")

            return

        if interaction.guild is None:

            await interaction.followup.send(
                "❌ Cette commande doit être utilisée " "dans un serveur.",
                ephemeral=True,
            )

            return

        embed = discord.Embed(
            title="🟣 Streamers",
            color=discord.Color.purple(),
        )

        for (
            discord_user_id,
            twitch_username,
            last_live_status,
        ) in streamers:

            member = interaction.guild.get_member(discord_user_id)

            if member:
                discord_name = member.mention
            else:
                discord_name = f"<@{discord_user_id}>"

            try:

                stream = await self.twitch_service.get_stream(twitch_username)

                is_live = stream is not None

            except Exception as error:

                print(f"⚠️ Twitch /streamers " f"{twitch_username}: {error}")

                is_live = bool(last_live_status)

            status = "🟢 **LIVE**" if is_live else "🔴 Offline"

            embed.add_field(
                name=twitch_username,
                value=(f"{discord_name}\n" f"{status}"),
                inline=True,
            )

        await interaction.followup.send(embed=embed)

    # =====================================================
    # /ADD-STREAMER
    # =====================================================

    @app_commands.command(name="add-streamer", description="Ajoute un streamer Twitch.")
    @app_commands.describe(
        user="Utilisateur Discord",
        twitch_username="Nom Twitch",
    )
    @has_required_role()
    async def add_streamer(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        twitch_username: str,
    ) -> None:

        await interaction.response.defer(ephemeral=True)

        twitch_username = twitch_username.strip().lower()

        if not twitch_username:

            await interaction.followup.send(
                "❌ Le nom Twitch est vide.",
                ephemeral=True,
            )

            return

        try:

            exists = await self.twitch_service.user_exists(twitch_username)

        except Exception as error:

            print(f"❌ Twitch API : {error}")

            await interaction.followup.send(
                "❌ Impossible de vérifier " "le compte Twitch.",
                ephemeral=True,
            )

            return

        if not exists:

            await interaction.followup.send(
                f"❌ Le compte Twitch " f"**{twitch_username}** " f"n'existe pas.",
                ephemeral=True,
            )

            return

        success = await self.database.add_streamer(
            user.id,
            twitch_username,
        )

        if not success:

            await interaction.followup.send(
                "❌ Impossible d'ajouter " "ce streamer.",
                ephemeral=True,
            )

            return

        await interaction.followup.send(
            f"✅ **{twitch_username}** " f"a été associé à {user.mention}.",
            ephemeral=True,
        )

    # =====================================================
    # /UPDATE-STREAMER
    # =====================================================

    @app_commands.command(
        name="update-streamer",
        description="Modifie le streamer Twitch d'un utilisateur.",
    )
    @app_commands.describe(
        user="Utilisateur Discord",
        new_username="Nouveau nom Twitch",
    )
    @has_required_role()
    async def update_streamer(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        new_username: str,
    ) -> None:

        await interaction.response.defer(ephemeral=True)

        new_username = new_username.strip().lower()

        if not new_username:

            await interaction.followup.send(
                "❌ Le nom Twitch est vide.",
                ephemeral=True,
            )
            return

        try:

            exists = await self.twitch_service.user_exists(new_username)

        except Exception as error:

            print(f"❌ Twitch API : {error}")

            await interaction.followup.send(
                "❌ Impossible de vérifier " "le compte Twitch.",
                ephemeral=True,
            )

            return

        if not exists:

            await interaction.followup.send(
                f"❌ Le compte Twitch " f"**{new_username}** n'existe pas.",
                ephemeral=True,
            )

            return

        success = await self.database.update_streamer(
            user.id,
            new_username,
        )

        if not success:

            await interaction.followup.send(
                f"❌ Aucun streamer Twitch " f"n'est associé à {user.mention}.",
                ephemeral=True,
            )

            return

        # Important :
        # on remet le statut à offline afin que le watcher
        # puisse détecter le nouveau compte correctement.
        await self.database.update_live_status(
            user.id,
            False,
        )

        await interaction.followup.send(
            f"✅ Le compte Twitch de "
            f"{user.mention} est maintenant "
            f"**{new_username}**.",
            ephemeral=True,
        )

    # =====================================================
    # /DELETE-STREAMER
    # =====================================================

    @app_commands.command(
        name="delete-streamer", description="Supprime un streamer Twitch."
    )
    @app_commands.describe(user="Utilisateur Discord à supprimer")
    @has_required_role()
    async def delete_streamer(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ) -> None:

        await interaction.response.defer(ephemeral=True)

        success = await self.database.delete_streamer(user.id)

        if not success:

            await interaction.followup.send(
                f"❌ Aucun streamer Twitch " f"n'est associé à {user.mention}.",
                ephemeral=True,
            )

            return

        await interaction.followup.send(
            f"🗑️ Le streamer Twitch associé à " f"{user.mention} a été supprimé.",
            ephemeral=True,
        )

    # =====================================================
    # STREAM WATCHER
    # =====================================================

    @tasks.loop(minutes=2)
    async def check_streamers(
        self,
    ) -> None:

        try:

            streamers = await self.database.get_all_streamers()

            if not streamers:
                return

            guild = self.bot.get_guild(config.GUILD_ID)

            if guild is None:
                return

            channel = guild.get_channel(config.TWITCH_NOTIFICATIONS_CHANNEL_ID)

            if not isinstance(
                channel,
                discord.TextChannel,
            ):
                print(
                    "⚠️ Salon Twitch introuvable : "
                    f"{config.TWITCH_NOTIFICATIONS_CHANNEL_ID}"
                )

                return

            for (
                discord_user_id,
                twitch_username,
                last_live_status,
            ) in streamers:

                try:

                    stream = await self.twitch_service.get_stream(twitch_username)

                    is_live = stream is not None
                    was_live = bool(last_live_status)

                    # =====================================
                    # OFFLINE -> LIVE
                    # =====================================

                    if is_live and not was_live:

                        await self.send_live_notification(
                            channel,
                            discord_user_id,
                            twitch_username,
                            stream,
                        )

                        await self.database.update_live_status(
                            discord_user_id,
                            True,
                        )

                        print(f"🟣 {twitch_username} " f"est maintenant LIVE.")

                    # =====================================
                    # LIVE -> OFFLINE
                    # =====================================

                    elif not is_live and was_live:

                        await self.database.update_live_status(
                            discord_user_id,
                            False,
                        )

                        print(f"⚫ {twitch_username} " f"est maintenant OFFLINE.")

                except Exception as error:

                    print(
                        "❌ Erreur vérification Twitch " f"{twitch_username}: {error}"
                    )

        except Exception as error:

            print("❌ Erreur Twitch watcher : " f"{error}")

    # =====================================================
    # WAIT BOT
    # =====================================================

    @check_streamers.before_loop
    async def before_check_streamers(
        self,
    ) -> None:

        await self.bot.wait_until_ready()

    # =====================================================
    # NOTIFICATION
    # =====================================================

    async def send_live_notification(
        self,
        channel: discord.TextChannel,
        discord_user_id: int,
        twitch_username: str,
        stream: dict,
    ) -> None:

        member = channel.guild.get_member(discord_user_id)

        mention = member.mention if member else f"<@{discord_user_id}>"

        title = stream.get("title") or "Live Twitch"

        game_name = stream.get("game_name") or "Aucun jeu"

        viewer_count = stream.get("viewer_count", 0)

        thumbnail_url = (
            stream.get("thumbnail_url", "")
            .replace("{width}", "1280")
            .replace("{height}", "720")
        )

        embed = discord.Embed(
            title=(f"🟣 {twitch_username} " f"est en LIVE !"),
            description=title,
            color=discord.Color.purple(),
            url=("https://www.twitch.tv/" f"{twitch_username}"),
        )

        embed.add_field(
            name="🎮 Jeu",
            value=game_name,
            inline=True,
        )

        embed.add_field(
            name="👀 Viewers",
            value=str(viewer_count),
            inline=True,
        )

        embed.add_field(
            name="Discord",
            value=mention,
            inline=True,
        )

        if thumbnail_url:

            # Anti-cache Twitch
            separator = "&" if "?" in thumbnail_url else "?"

            embed.set_image(
                url=(
                    f"{thumbnail_url}"
                    f"{separator}"
                    f"cache={discord.utils.utcnow().timestamp()}"
                )
            )

        embed.set_footer(text="Twitch • K.R.O.T.E")

        view = discord.ui.View()

        view.add_item(
            discord.ui.Button(
                label="Regarder le live",
                emoji="🟣",
                style=discord.ButtonStyle.link,
                url=("https://www.twitch.tv/" f"{twitch_username}"),
            )
        )

        await channel.send(
            content=(f"🔴 {mention} est maintenant " f"en live !"),
            embed=embed,
            view=view,
        )

    # =====================================================
    # ERRORS
    # =====================================================

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:

        if isinstance(
            error,
            MissingRequiredRole,
        ):

            message = "❌ Tu n'as pas le rôle requis " "pour utiliser cette commande."

        else:

            print("❌ Erreur Twitch command : " f"{type(error).__name__}: {error}")

            message = (
                "❌ Une erreur est survenue pendant " "l'exécution de la commande."
            )

        try:

            if interaction.response.is_done():

                await interaction.followup.send(
                    message,
                    ephemeral=True,
                )

            else:

                await interaction.response.send_message(
                    message,
                    ephemeral=True,
                )

        except discord.NotFound:

            print("⚠️ Interaction Twitch expirée.")


async def setup(
    bot: commands.Bot,
) -> None:

    await bot.add_cog(
        TwitchCog(
            bot,
            bot.database,
            bot.twitch_service,
        )
    )
