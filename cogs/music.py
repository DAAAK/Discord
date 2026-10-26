import asyncio
import random

from dataclasses import dataclass
from typing import Optional

import discord
import yt_dlp

from discord import app_commands
from discord.ext import commands

import config
from utils.checks import channel_only, WrongChannel

# =========================================================
# YT-DLP
# =========================================================

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}


# =========================================================
# FFMPEG
# =========================================================

FFMPEG_OPTIONS = {
    "before_options": (
        "-reconnect 1 " "-reconnect_streamed 1 " "-reconnect_delay_max 5"
    ),
    "options": "-vn",
}


# =========================================================
# TRACK
# =========================================================


@dataclass
class MusicTrack:
    query: str
    title: str
    webpage_url: Optional[str]
    thumbnail: Optional[str]
    duration: Optional[int]
    uploader: str
    requester_id: int


# =========================================================
# ÉTAT DU LECTEUR
# =========================================================


class GuildMusicState:

    def __init__(self):
        self.queue: list[MusicTrack] = []
        self.current: Optional[MusicTrack] = None
        self.lock = asyncio.Lock()

        # Message Discord contenant le player
        self.player_message: Optional[discord.Message] = None

        # Salon texte dans lequel le player est affiché
        self.text_channel_id: Optional[int] = None

        self.playlist_mode: bool = False
        self.shuffle_enabled: bool = False


class MusicPlayerView(discord.ui.View):

    def __init__(
        self,
        cog: "MusicCog",
        guild_id: int,
    ):
        super().__init__(timeout=None)

        self.cog = cog
        self.guild_id = guild_id

        # Récupère l'état AVANT de l'utiliser
        state = self.cog.get_state(guild_id)

        # Le bouton Random apparaît uniquement
        # lorsqu'une playlist est en cours
        if not state.playlist_mode:
            self.remove_item(self.shuffle)

        elif state.shuffle_enabled:
            self.shuffle.style = discord.ButtonStyle.success
            self.shuffle.label = "Random ON"

        else:
            self.shuffle.style = discord.ButtonStyle.secondary
            self.shuffle.label = "Random"

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:

        guild = interaction.guild

        if guild is None:
            return False

        # User must be a member of the server
        if not isinstance(interaction.user, discord.Member):
            return False

        voice_client = guild.voice_client

        # Bot is not connected to voice
        if voice_client is None or voice_client.channel is None:

            await interaction.response.send_message(
                "❌ Le bot n'est connecté à aucun salon vocal.",
                ephemeral=True,
            )
            return False

        # User is not in a voice channel
        if interaction.user.voice is None or interaction.user.voice.channel is None:

            await interaction.response.send_message(
                "❌ Tu dois être dans le salon vocal du bot "
                "pour utiliser le player.",
                ephemeral=True,
            )
            return False

        # User is in another voice channel
        if interaction.user.voice.channel.id != voice_client.channel.id:

            await interaction.response.send_message(
                "❌ Tu dois être dans le même salon vocal "
                "que le bot pour utiliser le player.",
                ephemeral=True,
            )
            return False

        return True

    # =====================================================
    # PAUSE / RESUME
    # =====================================================

    @discord.ui.button(
        label="Pause",
        emoji="⏸️",
        style=discord.ButtonStyle.secondary,
        custom_id="music:pause_resume",
    )
    async def pause_resume(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:

        guild = interaction.guild

        if guild is None:
            return

        voice_client = guild.voice_client

        if voice_client is None:

            await interaction.response.send_message(
                "❌ Je ne suis pas connecté au vocal.",
                ephemeral=True,
            )
            return

        if voice_client.is_paused():

            voice_client.resume()

            button.label = "Pause"
            button.emoji = "⏸️"

            await interaction.response.edit_message(view=self)

            return

        if voice_client.is_playing():

            voice_client.pause()

            button.label = "Reprendre"
            button.emoji = "▶️"

            await interaction.response.edit_message(view=self)

            return

        await interaction.response.send_message(
            "❌ Aucune musique en cours.",
            ephemeral=True,
        )

    # =====================================================
    # SKIP
    # =====================================================

    @discord.ui.button(
        label="Skip",
        emoji="⏭️",
        style=discord.ButtonStyle.primary,
        custom_id="music:skip",
    )
    async def skip(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:

        # Acquitte silencieusement le clic
        await interaction.response.defer()

        guild = interaction.guild

        if guild is None:
            return

        voice_client = guild.voice_client

        if voice_client is None:
            return

        if not voice_client.is_playing() and not voice_client.is_paused():
            return

        # Déclenche after_playing()
        # qui lancera automatiquement le suivant.
        voice_client.stop()

    # =====================================================
    # STOP
    # =====================================================

    @discord.ui.button(
        label="Stop",
        emoji="⏹️",
        style=discord.ButtonStyle.danger,
        custom_id="music:stop",
    )
    async def stop(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:

        # Acquitte silencieusement le clic
        await interaction.response.defer()

        guild = interaction.guild

        if guild is None:
            return

        state = self.cog.get_state(self.guild_id)

        # Important : vider la queue AVANT stop()
        # pour empêcher le lancement du suivant.
        state.queue.clear()
        state.current = None
        state.playlist_mode = False
        state.shuffle_enabled = False

        voice_client = guild.voice_client

        if voice_client is not None:

            if voice_client.is_playing() or voice_client.is_paused():
                voice_client.stop()

        # Actualise uniquement l'embed principal
        await self.cog.update_player_message(guild)

    # =====================================================
    # QUEUE
    # =====================================================

    @discord.ui.button(
        label="Queue",
        emoji="📜",
        style=discord.ButtonStyle.secondary,
        custom_id="music:queue",
    )
    async def queue(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:

        state = self.cog.get_state(self.guild_id)

        if not state.queue:

            await interaction.response.send_message(
                "📭 La file d'attente est vide.",
                ephemeral=True,
            )
            return

        lines = []

        for index, track in enumerate(
            state.queue[:10],
            start=1,
        ):

            lines.append(
                f"`{index}.` "
                f"**{track.title}** "
                f"`{self.cog.format_duration(track.duration)}`"
            )

        if len(state.queue) > 10:

            lines.append(f"\n… et " f"{len(state.queue) - 10} " f"autre(s).")

        embed = discord.Embed(
            title="🎶 File d'attente",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    # =====================================================
    # LEAVE
    # =====================================================

    @discord.ui.button(
        label="Leave",
        emoji="🔌",
        style=discord.ButtonStyle.danger,
        custom_id="music:leave",
    )
    async def leave(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:

        await interaction.response.defer()

        guild = interaction.guild

        if guild is None:
            return

        state = self.cog.get_state(self.guild_id)

        # Vide complètement le lecteur
        state.queue.clear()
        state.current = None
        state.playlist_mode = False
        state.shuffle_enabled = False

        voice_client = guild.voice_client

        if voice_client is not None:
            await voice_client.disconnect()

        # Supprime complètement l'embed/player
        if state.player_message is not None:

            try:
                await state.player_message.delete()

            except discord.NotFound:
                pass

            except discord.HTTPException as error:
                print(f"❌ Suppression player : {error}")

        # Important :
        # on oublie l'ancien message pour que
        # le prochain /play en crée un nouveau.
        state.player_message = None
        state.text_channel_id = None

    @discord.ui.button(
        label="Random",
        emoji="🔀",
        style=discord.ButtonStyle.secondary,
        custom_id="music:shuffle",
    )
    async def shuffle(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:

        state = self.cog.get_state(self.guild_id)

        if not state.playlist_mode:

            await interaction.response.send_message(
                "❌ Le mode aléatoire est disponible " "uniquement pour les playlists.",
                ephemeral=True,
            )
            return

        if len(state.queue) < 2:

            await interaction.response.send_message(
                "❌ Il n'y a pas assez de morceaux " "dans la file d'attente.",
                ephemeral=True,
            )
            return

        # Active / désactive
        state.shuffle_enabled = not state.shuffle_enabled

        if state.shuffle_enabled:
            random.shuffle(state.queue)

        await interaction.response.defer()

        await self.cog.update_player_message(interaction.guild)


# =========================================================
# MUSIC COG
# =========================================================


class MusicCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Une queue indépendante par serveur Discord
        self.states: dict[int, GuildMusicState] = {}

    # =========================================================
    # STATE
    # =========================================================

    def get_state(
        self,
        guild_id: int,
    ) -> GuildMusicState:

        if guild_id not in self.states:
            self.states[guild_id] = GuildMusicState()

        return self.states[guild_id]

    # =========================================================
    # FORMAT DURÉE
    # =========================================================

    @staticmethod
    def format_duration(
        duration: Optional[int],
    ) -> str:

        if not duration:
            return "Inconnue"

        hours, remainder = divmod(
            int(duration),
            3600,
        )

        minutes, seconds = divmod(
            remainder,
            60,
        )

        if hours > 0:
            return f"{hours}:" f"{minutes:02d}:" f"{seconds:02d}"

        return f"{minutes}:{seconds:02d}"

    # =========================================================
    # RECHERCHE YOUTUBE
    # =========================================================

    @staticmethod
    def search_track(
        query: str,
        requester_id: int,
    ) -> MusicTrack:

        search_query = query

        if not query.startswith(("http://", "https://")):
            search_query = f"ytsearch1:{query}"

        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:

            info = ydl.extract_info(
                search_query,
                download=False,
            )

            if "entries" in info:

                entries = [entry for entry in info["entries"] if entry is not None]

                if not entries:
                    raise RuntimeError("Aucun résultat trouvé.")

                info = entries[0]

            webpage_url = info.get(
                "webpage_url",
                info.get("original_url"),
            )

            # On garde l'URL YouTube réelle si possible.
            # Cela permet de réextraire un flux frais
            # lorsque le morceau commence.
            playback_query = webpage_url if webpage_url else query

            return MusicTrack(
                query=playback_query,
                title=info.get(
                    "title",
                    "Titre inconnu",
                ),
                webpage_url=webpage_url,
                thumbnail=info.get("thumbnail"),
                duration=info.get("duration"),
                uploader=info.get(
                    "uploader",
                    "Inconnu",
                ),
                requester_id=requester_id,
            )

    # =========================================================
    # EXTRACTION URL AUDIO
    # =========================================================

    @staticmethod
    def extract_stream_url(
        query: str,
    ) -> str:

        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:

            info = ydl.extract_info(
                query,
                download=False,
            )

            if "entries" in info:

                entries = [entry for entry in info["entries"] if entry is not None]

                if not entries:
                    raise RuntimeError("Aucun résultat audio.")

                info = entries[0]

            stream_url = info.get("url")

            if not stream_url:
                raise RuntimeError("Aucun flux audio trouvé.")

            return stream_url

    # =========================================================
    # EMBED TRACK
    # =========================================================

    def create_track_embed(
        self,
        track: MusicTrack,
        title: str,
    ) -> discord.Embed:

        embed = discord.Embed(
            title=title,
            color=discord.Color.blurple(),
        )

        if track.webpage_url:

            embed.description = f"[{track.title}]" f"({track.webpage_url})"

        else:

            embed.description = f"**{track.title}**"

        embed.add_field(
            name="Artiste",
            value=track.uploader,
            inline=True,
        )

        embed.add_field(
            name="Durée",
            value=self.format_duration(track.duration),
            inline=True,
        )

        embed.add_field(
            name="Demandé par",
            value=f"<@{track.requester_id}>",
            inline=True,
        )

        if track.thumbnail:

            embed.set_thumbnail(url=track.thumbnail)

        return embed

    def create_player_embed(
        self,
        state: GuildMusicState,
    ) -> discord.Embed:

        track = state.current

        if track is None:

            embed = discord.Embed(
                title="🎵 K.R.O.T.E Music",
                description="Aucune musique en cours.",
                color=discord.Color.dark_grey(),
            )

            embed.set_footer(text="Utilise /play pour lancer une musique")

            return embed

        embed = discord.Embed(
            title="🎧 Lecture en cours",
            color=discord.Color.blurple(),
        )

        if track.webpage_url:

            embed.description = f"### [{track.title}]" f"({track.webpage_url})"

        else:

            embed.description = f"### {track.title}"

        embed.add_field(
            name="🎤 Artiste",
            value=track.uploader,
            inline=True,
        )

        embed.add_field(
            name="⏱️ Durée",
            value=self.format_duration(track.duration),
            inline=True,
        )

        embed.add_field(
            name="👤 Demandé par",
            value=f"<@{track.requester_id}>",
            inline=True,
        )

        embed.add_field(
            name="📜 File d'attente",
            value=(f"{len(state.queue)} morceau(x)"),
            inline=True,
        )

        if state.queue:

            next_track = state.queue[0]

            embed.add_field(
                name="⏭️ À suivre",
                value=next_track.title,
                inline=True,
            )

        if track.thumbnail:

            embed.set_image(url=track.thumbnail)

        embed.set_footer(text="K.R.O.T.E Music Player")

        return embed

    async def update_player_message(
        self,
        guild: discord.Guild,
    ) -> None:

        state = self.get_state(guild.id)

        if state.text_channel_id is None:
            return

        channel = guild.get_channel(state.text_channel_id)

        if not isinstance(
            channel,
            discord.TextChannel,
        ):
            return

        embed = self.create_player_embed(state)

        view = MusicPlayerView(
            self,
            guild.id,
        )

        # ==========================================
        # Modifier le player existant
        # ==========================================

        if state.player_message:

            try:

                await state.player_message.edit(
                    embed=embed,
                    view=view,
                )

                return

            except discord.NotFound:

                state.player_message = None

            except discord.HTTPException as error:

                print(f"❌ Update player : {error}")

        # ==========================================
        # Sinon créer le player
        # ==========================================

        try:

            state.player_message = await channel.send(
                embed=embed,
                view=view,
            )

        except discord.HTTPException as error:

            print(f"❌ Création player : {error}")

    # =========================================================
    # LECTURE DU PROCHAIN MORCEAU
    # =========================================================

    async def play_next(
        self,
        guild: discord.Guild,
    ) -> None:

        state = self.get_state(guild.id)

        async with state.lock:

            voice_client = guild.voice_client

            if voice_client is None:
                state.current = None
                return

            # Une musique est déjà active
            if voice_client.is_playing() or voice_client.is_paused():
                return

            # Queue terminée
            if not state.queue:
                state.current = None
                return

            track = state.queue.pop(0)
            state.current = track

            try:

                stream_url = await asyncio.to_thread(
                    self.extract_stream_url,
                    track.query,
                )

                source = discord.FFmpegOpusAudio(
                    stream_url,
                    executable=config.FFMPEG_PATH,
                    **FFMPEG_OPTIONS,
                )

            except Exception as error:

                print("❌ Impossible de préparer " f"{track.title} : {error}")

                state.current = None

                # Essaie le morceau suivant
                asyncio.create_task(self.play_next(guild))

                return

            def after_playing(
                error: Optional[Exception],
            ) -> None:

                if error:

                    print("❌ Erreur lecture audio : " f"{error}")

                # after() n'est pas exécuté dans
                # l'event loop asyncio.
                future = asyncio.run_coroutine_threadsafe(
                    self.track_finished(guild),
                    self.bot.loop,
                )

                try:
                    future.result()

                except Exception as future_error:

                    print(
                        "❌ Erreur passage au " "morceau suivant : " f"{future_error}"
                    )

            try:

                voice_client.play(
                    source,
                    after=after_playing,
                )

                await self.update_player_message(guild)

            except Exception as error:

                print(f"❌ Lecture Discord : {error}")

                state.current = None

                asyncio.create_task(self.play_next(guild))

    # =========================================================
    # FIN DU MORCEAU
    # =========================================================

    async def track_finished(
        self,
        guild: discord.Guild,
    ) -> None:

        state = self.get_state(guild.id)

        state.current = None

        # Petit délai pour laisser Discord
        # terminer proprement l'ancienne source.
        await asyncio.sleep(0.5)

        await self.play_next(guild)

        await self.update_player_message(guild)

    # =========================================================
    # PLAY
    # =========================================================

    @app_commands.command(
        name="play",
        description=("Joue une musique ou l'ajoute " "à la file d'attente."),
    )
    @app_commands.describe(recherche="Nom de la musique ou URL YouTube")
    @channel_only(config.MUSIC_CHANNEL_ID)
    async def play(
        self,
        interaction: discord.Interaction,
        recherche: str,
    ) -> None:

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ Cette commande doit être " "utilisée dans un serveur.",
                ephemeral=True,
            )
            return

        if not isinstance(
            interaction.user,
            discord.Member,
        ):

            await interaction.response.send_message(
                "❌ Impossible de récupérer " "ton salon vocal.",
                ephemeral=True,
            )
            return

        if interaction.user.voice is None or interaction.user.voice.channel is None:

            await interaction.response.send_message(
                "❌ Tu dois être dans " "un salon vocal.",
                ephemeral=True,
            )
            return

        voice_channel = interaction.user.voice.channel

        await interaction.response.defer()

        voice_client = interaction.guild.voice_client

        # ==========================================
        # Connexion au vocal
        # ==========================================

        if voice_client is None:

            try:

                voice_client = await voice_channel.connect()

            except Exception as error:

                print(f"❌ Connexion vocal : {error}")

                await interaction.followup.send(
                    "❌ Je n'arrive pas à rejoindre " "le salon vocal."
                )
                return

        elif voice_client.channel != voice_channel:

            await interaction.followup.send(
                "❌ Je suis déjà utilisé dans " "un autre salon vocal.",
                ephemeral=True,
            )
            return

        # ==========================================
        # Recherche
        # ==========================================

        try:

            track = await asyncio.to_thread(
                self.search_track,
                recherche,
                interaction.user.id,
            )

        except Exception as error:

            print(f"❌ yt-dlp : {error}")

            await interaction.followup.send(
                "❌ Impossible de trouver " "cette musique."
            )
            return

        state = self.get_state(interaction.guild.id)

        state.text_channel_id = interaction.channel_id

        # Est-ce qu'un morceau joue déjà ?
        already_playing = (
            voice_client.is_playing()
            or voice_client.is_paused()
            or state.current is not None
        )

        state.queue.append(track)

        # ==========================================
        # Réponse
        # ==========================================

        if already_playing:

            # Le morceau est simplement ajouté à la queue.
            # Aucun nouvel embed/message n'est envoyé.
            await self.update_player_message(interaction.guild)

            # On valide quand même l'interaction Discord
            # sans polluer le salon.
            try:
                await interaction.delete_original_response()
            except discord.NotFound:
                pass

        else:

            # Premier morceau :
            # play_next() créera / actualisera le player principal.
            await self.play_next(interaction.guild)

            try:
                await interaction.delete_original_response()
            except discord.NotFound:
                pass

    # =========================================================
    # PAUSE
    # =========================================================

    @app_commands.command(
        name="pause",
        description="Met la musique en pause.",
    )
    @channel_only(config.MUSIC_CHANNEL_ID)
    async def pause(
        self,
        interaction: discord.Interaction,
    ) -> None:

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ Commande indisponible.",
                ephemeral=True,
            )
            return

        voice_client = interaction.guild.voice_client

        if voice_client is None or not voice_client.is_playing():

            await interaction.response.send_message(
                "❌ Aucune musique n'est " "en cours de lecture.",
                ephemeral=True,
            )
            return

        voice_client.pause()

        await interaction.response.send_message("⏸️ Musique en pause.")

    # =========================================================
    # RESUME
    # =========================================================

    @app_commands.command(
        name="resume",
        description="Reprend la musique.",
    )
    @channel_only(config.MUSIC_CHANNEL_ID)
    async def resume(
        self,
        interaction: discord.Interaction,
    ) -> None:

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ Commande indisponible.",
                ephemeral=True,
            )
            return

        voice_client = interaction.guild.voice_client

        if voice_client is None or not voice_client.is_paused():

            await interaction.response.send_message(
                "❌ La musique n'est " "pas en pause.",
                ephemeral=True,
            )
            return

        voice_client.resume()

        await interaction.response.send_message("▶️ Lecture reprise.")

    # =========================================================
    # SKIP
    # =========================================================

    @app_commands.command(
        name="skip",
        description="Passe au morceau suivant.",
    )
    @channel_only(config.MUSIC_CHANNEL_ID)
    async def skip(
        self,
        interaction: discord.Interaction,
    ) -> None:

        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None:
            await interaction.delete_original_response()
            return

        voice_client = interaction.guild.voice_client

        if voice_client is None or (
            not voice_client.is_playing() and not voice_client.is_paused()
        ):
            await interaction.delete_original_response()
            return

        # stop() déclenche after_playing(),
        # qui lancera automatiquement le suivant.
        voice_client.stop()

        await interaction.delete_original_response()

    # =========================================================
    # STOP
    # =========================================================

    @app_commands.command(
        name="stop",
        description="Arrête la musique et vide la file d'attente.",
    )
    @channel_only(config.MUSIC_CHANNEL_ID)
    async def stop(
        self,
        interaction: discord.Interaction,
    ) -> None:

        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None:
            await interaction.delete_original_response()
            return

        state = self.get_state(interaction.guild.id)

        # On vide d'abord la queue pour empêcher
        # le lancement d'un autre morceau.
        state.queue.clear()
        state.playlist_mode = False
        state.shuffle_enabled = False

        voice_client = interaction.guild.voice_client

        if voice_client is not None:

            if voice_client.is_playing() or voice_client.is_paused():
                voice_client.stop()

        state.current = None

        # Actualise uniquement le player principal
        await self.update_player_message(interaction.guild)

        # Aucune réponse visible
        try:
            await interaction.delete_original_response()
        except discord.NotFound:
            pass

    # =========================================================
    # QUEUE
    # =========================================================

    @app_commands.command(
        name="queue",
        description="Affiche la file d'attente.",
    )
    @channel_only(config.MUSIC_CHANNEL_ID)
    async def queue(
        self,
        interaction: discord.Interaction,
    ) -> None:

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ Commande indisponible.",
                ephemeral=True,
            )
            return

        state = self.get_state(interaction.guild.id)

        if state.current is None and not state.queue:

            await interaction.response.send_message(
                "📭 La file d'attente est vide.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🎶 File d'attente",
            color=discord.Color.blurple(),
        )

        if state.current:

            current = state.current

            if current.webpage_url:

                current_text = f"[{current.title}]" f"({current.webpage_url})"

            else:

                current_text = f"**{current.title}**"

            embed.add_field(
                name="▶️ En cours",
                value=(
                    f"{current_text}\n"
                    f"`{self.format_duration(current.duration)}` "
                    f"• <@{current.requester_id}>"
                ),
                inline=False,
            )

        if state.queue:

            lines = []

            # Discord limite la taille
            # d'un field, donc max 10 affichés.
            for index, track in enumerate(
                state.queue[:10],
                start=1,
            ):

                lines.append(
                    f"`{index}.` "
                    f"**{track.title}** "
                    f"`{self.format_duration(track.duration)}`"
                )

            if len(state.queue) > 10:

                lines.append(
                    f"\n… et " f"{len(state.queue) - 10} " f"autre(s) morceau(x)."
                )

            embed.add_field(
                name="⏭️ À suivre",
                value="\n".join(lines),
                inline=False,
            )

        embed.set_footer(text=(f"{len(state.queue)} morceau(x) " "en attente"))

        await interaction.response.send_message(embed=embed)

    # =========================================================
    # LEAVE
    # =========================================================

    @app_commands.command(
        name="leave",
        description="Déconnecte le bot du salon vocal.",
    )
    @channel_only(config.MUSIC_CHANNEL_ID)
    async def leave(
        self,
        interaction: discord.Interaction,
    ) -> None:

        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None:
            await interaction.delete_original_response()
            return

        state = self.get_state(interaction.guild.id)

        state.queue.clear()
        state.current = None
        state.playlist_mode = False
        state.shuffle_enabled = False

        voice_client = interaction.guild.voice_client

        if voice_client is not None:
            await voice_client.disconnect()

        # Supprime le player principal
        if state.player_message is not None:

            try:
                await state.player_message.delete()

            except discord.NotFound:
                pass

            except discord.HTTPException as error:
                print(f"❌ Suppression player : {error}")

        state.player_message = None
        state.text_channel_id = None

        # Aucun message de confirmation
        try:
            await interaction.delete_original_response()
        except discord.NotFound:
            pass

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:

        if isinstance(error, WrongChannel):

            message = (
                f"❌ Les commandes musique sont uniquement "
                f"disponibles dans <#{error.channel_id}>."
            )

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

            return

        print(f"❌ Erreur commande musique : {error}")


# =========================================================
# SETUP
# =========================================================


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MusicCog(bot))
