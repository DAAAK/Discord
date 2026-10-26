import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import config
from cogs.music import MusicCog, MusicTrack
from utils.checks import channel_only


class PlaylistCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # =========================================================
    # DATABASE
    # =========================================================

    @property
    def db(
        self,
    ):
        return self.bot.database

    # =========================================================
    # MUSIC COG
    # =========================================================

    def get_music_cog(self) -> MusicCog | None:

        cog = self.bot.get_cog("MusicCog")

        if isinstance(cog, MusicCog):
            return cog

        return None

    # =========================================================
    # PLAYLIST AUTOCOMPLETE
    # =========================================================

    async def playlist_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:

        if interaction.guild is None:
            return []

        playlists = await self.db.get_user_playlists(
            interaction.guild.id,
            interaction.user.id,
        )

        current = current.lower()

        choices = []

        for playlist in playlists:

            name = playlist["name"]

            if current in name.lower():
                choices.append(
                    app_commands.Choice(
                        name=name,
                        value=name,
                    )
                )

        return choices[:25]

    # =========================================================
    # PLAY
    # =========================================================

    @app_commands.command(
        name="playlist-play",
        description="Ajoute une de tes playlists au lecteur.",
    )
    @app_commands.describe(
        playlist="Playlist à écouter",
    )
    @app_commands.autocomplete(playlist=playlist_autocomplete)
    @channel_only(config.MUSIC_CHANNEL_ID)
    async def playlist_play(
        self,
        interaction: discord.Interaction,
        playlist: str,
    ) -> None:

        guild = interaction.guild

        if guild is None:
            return

        if not isinstance(
            interaction.user,
            discord.Member,
        ):
            return

        # -----------------------------------------------------
        # Vérifie le vocal de l'utilisateur
        # -----------------------------------------------------

        if interaction.user.voice is None or interaction.user.voice.channel is None:
            await interaction.response.send_message(
                "❌ Tu dois être dans un salon vocal.",
                ephemeral=True,
            )
            return

        user_voice_channel = interaction.user.voice.channel

        # -----------------------------------------------------
        # Récupère le MusicCog
        # -----------------------------------------------------

        music = self.get_music_cog()

        if music is None:
            await interaction.response.send_message(
                "❌ Le système de musique est indisponible.",
                ephemeral=True,
            )
            return

        # -----------------------------------------------------
        # Récupère la playlist
        # -----------------------------------------------------

        db_playlist = await self.db.get_playlist(
            guild.id,
            interaction.user.id,
            playlist,
        )

        if db_playlist is None:
            await interaction.response.send_message(
                "❌ Cette playlist n'existe pas.",
                ephemeral=True,
            )
            return

        tracks = await self.db.get_playlist_tracks(db_playlist["id"])

        if not tracks:
            await interaction.response.send_message(
                f"📭 **{db_playlist['name']}** est vide.",
                ephemeral=True,
            )
            return

        # -----------------------------------------------------
        # Connexion vocale
        # -----------------------------------------------------

        voice_client = guild.voice_client

        if voice_client is None:

            try:
                voice_client = await user_voice_channel.connect()

            except Exception as error:
                print(f"❌ Connexion vocal playlist : {error}")

                await interaction.response.send_message(
                    "❌ Impossible de rejoindre ton salon vocal.",
                    ephemeral=True,
                )
                return

        elif voice_client.channel.id != user_voice_channel.id:

            await interaction.response.send_message(
                "❌ Je suis déjà connecté dans un autre " "salon vocal.",
                ephemeral=True,
            )
            return

        # -----------------------------------------------------
        # On prépare la queue existante
        # -----------------------------------------------------

        state = music.get_state(guild.id)

        state.text_channel_id = interaction.channel_id

        # -----------------------------------------------------
        # Conversion DB -> MusicTrack
        # -----------------------------------------------------

        playlist_tracks = []

        for db_track in tracks:

            track = MusicTrack(
                query=db_track["url"],
                title=db_track["title"],
                webpage_url=db_track["url"],
                thumbnail=db_track["thumbnail"],
                duration=db_track["duration"],
                uploader=(db_track["uploader"] or "Inconnu"),
                requester_id=interaction.user.id,
            )

            playlist_tracks.append(track)

        # -----------------------------------------------------
        # Ajout à LA queue Music existante
        # -----------------------------------------------------
        state.playlist_mode = True
        state.shuffle_enabled = False

        state.queue.extend(playlist_tracks)

        await interaction.response.defer(
            ephemeral=True,
        )

        # -----------------------------------------------------
        # Lance uniquement si rien ne joue
        # -----------------------------------------------------

        if (
            voice_client is not None
            and not voice_client.is_playing()
            and not voice_client.is_paused()
            and state.current is None
        ):
            await music.play_next(guild)

        # Actualise le player existant
        await music.update_player_message(guild)

        await interaction.followup.send(
            f"▶️ **{db_playlist['name']}** ajoutée au lecteur "
            f"avec **{len(playlist_tracks)} morceau(x)**.",
            ephemeral=True,
        )

    # =========================================================
    # CREATE
    # =========================================================

    @app_commands.command(
        name="playlist-create",
        description="Crée une nouvelle playlist.",
    )
    @app_commands.describe(
        nom="Nom de la playlist",
    )
    @channel_only(config.MUSIC_CHANNEL_ID)
    async def playlist_create(
        self,
        interaction: discord.Interaction,
        nom: str,
    ) -> None:

        if interaction.guild is None:
            return

        nom = nom.strip()

        if not nom:
            await interaction.response.send_message(
                "❌ Le nom de la playlist est invalide.",
                ephemeral=True,
            )
            return

        if len(nom) > 100:
            await interaction.response.send_message(
                "❌ Le nom ne peut pas dépasser 100 caractères.",
                ephemeral=True,
            )
            return

        created = await self.db.create_playlist(
            interaction.guild.id,
            interaction.user.id,
            nom,
        )

        if not created:
            await interaction.response.send_message(
                f"❌ Tu as déjà une playlist nommée **{nom}**.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"✅ Playlist **{nom}** créée.",
            ephemeral=True,
        )

    # =========================================================
    # LIST
    # =========================================================

    @app_commands.command(
        name="playlists",
        description="Affiche tes playlists.",
    )
    @channel_only(config.MUSIC_CHANNEL_ID)
    async def playlists(
        self,
        interaction: discord.Interaction,
    ) -> None:

        if interaction.guild is None:
            return

        playlists = await self.db.get_user_playlists(
            interaction.guild.id,
            interaction.user.id,
        )

        if not playlists:
            await interaction.response.send_message(
                "📭 Tu n'as aucune playlist.",
                ephemeral=True,
            )
            return

        lines = []

        for playlist in playlists:
            lines.append(
                f"🎵 **{playlist['name']}** " f"• {playlist['trackcount']} morceau(x)"
            )

        embed = discord.Embed(
            title="🎶 Mes playlists",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    # =========================================================
    # ADD
    # =========================================================

    @app_commands.command(
        name="playlist-add",
        description="Ajoute une musique à une playlist.",
    )
    @app_commands.describe(
        playlist="Nom de la playlist",
        recherche="Nom de la musique ou URL YouTube",
    )
    @app_commands.autocomplete(playlist=playlist_autocomplete)
    @channel_only(config.MUSIC_CHANNEL_ID)
    async def playlist_add(
        self,
        interaction: discord.Interaction,
        playlist: str,
        recherche: str,
    ) -> None:

        if interaction.guild is None:
            return

        music = self.get_music_cog()

        if music is None:
            await interaction.response.send_message(
                "❌ Le système de musique est indisponible.",
                ephemeral=True,
            )
            return

        db_playlist = await self.db.get_playlist(
            interaction.guild.id,
            interaction.user.id,
            playlist,
        )

        if db_playlist is None:
            await interaction.response.send_message(
                "❌ Cette playlist n'existe pas.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True,
        )

        try:
            track = await asyncio.to_thread(
                music.search_track,
                recherche,
                interaction.user.id,
            )

        except Exception as error:
            print(f"❌ Playlist yt-dlp : {error}")

            await interaction.followup.send(
                "❌ Impossible de trouver cette musique.",
                ephemeral=True,
            )
            return

        if track.webpage_url is None:
            await interaction.followup.send(
                "❌ Impossible de récupérer l'URL de cette musique.",
                ephemeral=True,
            )
            return

        await self.db.add_playlist_track(
            db_playlist["id"],
            track.title,
            track.webpage_url,
            track.uploader,
            track.duration,
            track.thumbnail,
        )

        await interaction.followup.send(
            f"✅ **{track.title}** ajouté à " f"**{db_playlist['name']}**.",
            ephemeral=True,
        )

    # =========================================================
    # SHOW
    # =========================================================

    @app_commands.command(
        name="playlist-show",
        description="Affiche le contenu d'une playlist.",
    )
    @app_commands.describe(
        playlist="Nom de la playlist",
    )
    @app_commands.autocomplete(playlist=playlist_autocomplete)
    @channel_only(config.MUSIC_CHANNEL_ID)
    async def playlist_show(
        self,
        interaction: discord.Interaction,
        playlist: str,
    ) -> None:

        if interaction.guild is None:
            return

        db_playlist = await self.db.get_playlist(
            interaction.guild.id,
            interaction.user.id,
            playlist,
        )

        if db_playlist is None:
            await interaction.response.send_message(
                "❌ Cette playlist n'existe pas.",
                ephemeral=True,
            )
            return

        tracks = await self.db.get_playlist_tracks(db_playlist["id"])

        if not tracks:
            await interaction.response.send_message(
                f"📭 **{db_playlist['name']}** est vide.",
                ephemeral=True,
            )
            return

        music = self.get_music_cog()

        lines = []

        for track in tracks[:20]:

            duration = (
                music.format_duration(track["duration"]) if music is not None else "?"
            )

            lines.append(
                f"`{track['position']}.` " f"**{track['title']}** " f"`{duration}`"
            )

        if len(tracks) > 20:
            lines.append(f"\n… et {len(tracks) - 20} autre(s).")

        embed = discord.Embed(
            title=f"🎵 {db_playlist['name']}",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )

        embed.set_footer(text=f"{len(tracks)} morceau(x)")

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    # =========================================================
    # REMOVE TRACK
    # =========================================================

    @app_commands.command(
        name="playlist-remove",
        description="Retire une musique d'une playlist.",
    )
    @app_commands.describe(
        playlist="Nom de la playlist",
        position="Numéro de la musique",
    )
    @app_commands.autocomplete(playlist=playlist_autocomplete)
    @channel_only(config.MUSIC_CHANNEL_ID)
    async def playlist_remove(
        self,
        interaction: discord.Interaction,
        playlist: str,
        position: int,
    ) -> None:

        if interaction.guild is None:
            return

        db_playlist = await self.db.get_playlist(
            interaction.guild.id,
            interaction.user.id,
            playlist,
        )

        if db_playlist is None:
            await interaction.response.send_message(
                "❌ Cette playlist n'existe pas.",
                ephemeral=True,
            )
            return

        removed = await self.db.remove_playlist_track(
            db_playlist["id"],
            position,
        )

        if not removed:
            await interaction.response.send_message(
                "❌ Aucune musique à cette position.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "🗑️ Musique retirée de la playlist.",
            ephemeral=True,
        )

    # =========================================================
    # DELETE PLAYLIST
    # =========================================================

    @app_commands.command(
        name="playlist-delete",
        description="Supprime une de tes playlists.",
    )
    @app_commands.describe(
        playlist="Playlist à supprimer",
    )
    @app_commands.autocomplete(playlist=playlist_autocomplete)
    @channel_only(config.MUSIC_CHANNEL_ID)
    async def playlist_delete(
        self,
        interaction: discord.Interaction,
        playlist: str,
    ) -> None:

        if interaction.guild is None:
            return

        deleted = await self.db.delete_playlist(
            interaction.guild.id,
            interaction.user.id,
            playlist,
        )

        if not deleted:
            await interaction.response.send_message(
                "❌ Cette playlist n'existe pas.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"🗑️ Playlist **{playlist}** supprimée.",
            ephemeral=True,
        )

    # =========================================================
    # RENAME PLAYLIST
    # =========================================================

    @app_commands.command(
        name="playlist-rename",
        description="Renomme une de tes playlists.",
    )
    @app_commands.describe(
        playlist="Playlist à renommer",
        nouveau_nom="Nouveau nom",
    )
    @app_commands.autocomplete(playlist=playlist_autocomplete)
    @channel_only(config.MUSIC_CHANNEL_ID)
    async def playlist_rename(
        self,
        interaction: discord.Interaction,
        playlist: str,
        nouveau_nom: str,
    ) -> None:

        if interaction.guild is None:
            return

        nouveau_nom = nouveau_nom.strip()

        if not nouveau_nom:
            await interaction.response.send_message(
                "❌ Le nouveau nom est invalide.",
                ephemeral=True,
            )
            return

        if len(nouveau_nom) > 100:
            await interaction.response.send_message(
                "❌ Le nom ne peut pas dépasser 100 caractères.",
                ephemeral=True,
            )
            return

        existing = await self.db.get_playlist(
            interaction.guild.id,
            interaction.user.id,
            nouveau_nom,
        )

        if existing is not None:
            await interaction.response.send_message(
                f"❌ Tu as déjà une playlist nommée " f"**{nouveau_nom}**.",
                ephemeral=True,
            )
            return

        renamed = await self.db.rename_playlist(
            interaction.guild.id,
            interaction.user.id,
            playlist,
            nouveau_nom,
        )

        if not renamed:
            await interaction.response.send_message(
                "❌ Cette playlist n'existe pas.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"✏️ **{playlist}** renommée en " f"**{nouveau_nom}**.",
            ephemeral=True,
        )


async def setup(
    bot: commands.Bot,
) -> None:

    await bot.add_cog(PlaylistCog(bot))
