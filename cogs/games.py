import random

import discord
from discord import app_commands
from discord.ext import commands

import config

from utils.checks import (
    WrongChannel,
    channel_only,
)


class HangmanGame:

    MAX_ERRORS = 7

    def __init__(
        self,
        word: str,
        started_by: discord.Member,
    ):
        self.word = word.upper()
        self.started_by = started_by

        self.guessed_letters: set[str] = set()
        self.wrong_letters: set[str] = set()

        self.errors = 0
        self.finished = False

        self.message: discord.Message | None = None

    # =====================================================
    # DISPLAY WORD
    # =====================================================

    def display_word(self) -> str:

        result = []

        for char in self.word:

            if not char.isalpha():
                result.append(char)

            elif char in self.guessed_letters:
                result.append(char)

            else:
                result.append("_")

        return " ".join(result)

    # =====================================================
    # WIN
    # =====================================================

    def is_won(self) -> bool:

        for char in self.word:

            if char.isalpha() and char not in self.guessed_letters:
                return False

        return True

    # =====================================================
    # EMBED
    # =====================================================

    def create_embed(
        self,
        message: str | None = None,
    ) -> discord.Embed:

        if self.finished and self.is_won():

            color = discord.Color.green()
            title = "🏆 Hangman — Victoire !"

        elif self.finished:

            color = discord.Color.red()
            title = "💀 Hangman — Perdu !"

        else:

            color = discord.Color.blurple()
            title = "🎮 Hangman"

        embed = discord.Embed(
            title=title,
            color=color,
        )

        if self.finished and not self.is_won():

            word_display = (
                f"~~{self.display_word()}~~\n\n" f"💀 Le mot était : **{self.word}**"
            )

        else:

            word_display = f"```text\n" f"{self.display_word()}\n" f"```"

        embed.add_field(
            name="Mot",
            value=word_display,
            inline=False,
        )

        wrong = " ".join(sorted(self.wrong_letters)) if self.wrong_letters else "Aucune"

        embed.add_field(
            name="❌ Lettres incorrectes",
            value=wrong,
            inline=True,
        )

        embed.add_field(
            name="❤️ Essais",
            value=(f"**{self.MAX_ERRORS - self.errors}**" f"/{self.MAX_ERRORS}"),
            inline=True,
        )

        if message:
            embed.add_field(
                name="📢",
                value=message,
                inline=False,
            )

        embed.set_footer(text=(f"Partie lancée par " f"{self.started_by.display_name}"))

        return embed


class RPSChallengeView(discord.ui.View):

    def __init__(
        self,
        challenger: discord.Member,
        opponent: discord.Member,
        challenger_choice: str,
    ):
        super().__init__(timeout=60)

        self.challenger = challenger
        self.opponent = opponent
        self.challenger_choice = challenger_choice

        self.message: discord.Message | None = None
        self.finished = False

    # =====================================================
    # UTILS
    # =====================================================

    @staticmethod
    def get_name(choice: str) -> str:
        names = {
            "rock": "Pierre",
            "paper": "Papier",
            "scissors": "Ciseaux",
        }

        return names[choice]

    @staticmethod
    def get_emoji(choice: str) -> str:
        emojis = {
            "rock": "🪨",
            "paper": "📄",
            "scissors": "✂️",
        }

        return emojis[choice]

    @staticmethod
    def get_winner(
        challenger_choice: str,
        opponent_choice: str,
    ) -> str:

        if challenger_choice == opponent_choice:
            return "draw"

        challenger_wins = (
            (challenger_choice == "rock" and opponent_choice == "scissors")
            or (challenger_choice == "paper" and opponent_choice == "rock")
            or (challenger_choice == "scissors" and opponent_choice == "paper")
        )

        if challenger_wins:
            return "challenger"

        return "opponent"

    # =====================================================
    # INTERACTION CHECK
    # =====================================================

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:

        if interaction.user.id != self.opponent.id:

            await interaction.response.send_message(
                "❌ Ce duel ne t'est pas destiné.",
                ephemeral=True,
            )

            return False

        return True

    # =====================================================
    # PLAY
    # =====================================================

    async def play(
        self,
        interaction: discord.Interaction,
        opponent_choice: str,
    ) -> None:

        if self.finished:
            await interaction.response.send_message(
                "❌ Ce duel est déjà terminé.",
                ephemeral=True,
            )
            return

        self.finished = True

        winner = self.get_winner(
            self.challenger_choice,
            opponent_choice,
        )

        challenger_display = (
            f"{self.get_emoji(self.challenger_choice)} "
            f"**{self.get_name(self.challenger_choice)}**"
        )

        opponent_display = (
            f"{self.get_emoji(opponent_choice)} "
            f"**{self.get_name(opponent_choice)}**"
        )

        if winner == "draw":

            result = "🤝 **Égalité !**"
            color = discord.Color.orange()

        elif winner == "challenger":

            result = f"🏆 {self.challenger.mention} " f"**remporte le duel !**"

            color = discord.Color.green()

        else:

            result = f"🏆 {self.opponent.mention} " f"**remporte le duel !**"

            color = discord.Color.green()

        embed = discord.Embed(
            title="⚔️ Pierre • Papier • Ciseaux",
            description=(f"{self.challenger.mention} " f"VS {self.opponent.mention}"),
            color=color,
        )

        embed.add_field(
            name=self.challenger.display_name,
            value=challenger_display,
            inline=True,
        )

        embed.add_field(
            name=self.opponent.display_name,
            value=opponent_display,
            inline=True,
        )

        embed.add_field(
            name="Résultat",
            value=result,
            inline=False,
        )

        # Désactive tous les boutons
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

        await interaction.response.edit_message(
            embed=embed,
            view=self,
        )

        self.stop()

    # =====================================================
    # BUTTONS
    # =====================================================

    @discord.ui.button(
        label="Pierre",
        emoji="🪨",
        style=discord.ButtonStyle.secondary,
    )
    async def rock(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:

        await self.play(
            interaction,
            "rock",
        )

    @discord.ui.button(
        label="Papier",
        emoji="📄",
        style=discord.ButtonStyle.primary,
    )
    async def paper(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:

        await self.play(
            interaction,
            "paper",
        )

    @discord.ui.button(
        label="Ciseaux",
        emoji="✂️",
        style=discord.ButtonStyle.danger,
    )
    async def scissors(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:

        await self.play(
            interaction,
            "scissors",
        )

    # =====================================================
    # TIMEOUT
    # =====================================================

    async def on_timeout(self) -> None:

        if self.finished:
            return

        self.finished = True

        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

        if self.message is None:
            return

        embed = discord.Embed(
            title="⌛ Duel expiré",
            description=(
                f"{self.opponent.mention} n'a pas répondu "
                f"au défi de {self.challenger.mention}."
            ),
            color=discord.Color.dark_grey(),
        )

        try:
            await self.message.edit(
                embed=embed,
                view=self,
            )
        except discord.HTTPException:
            pass


class GamesCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.active_hangman_games: dict[int, HangmanGame] = {}

    HANGMAN_WORDS = [
        "NARUTO",
        "SASUKE",
        "MADARA",
        "ITACHI",
        "KAKASHI",
        "MINATO",
        "SAITAMA",
        "GENOS",
        "TANJIRO",
        "NEZUKO",
        "GOJO",
        "SUKUNA",
        "MEGUMI",
        "LUFFY",
        "ZORO",
        "SANJI",
        "SHANKS",
        "KAIDO",
        "DOFLAMINGO",
        "ICHIGO",
        "AIZEN",
        "EREN",
        "LEVI",
        "MIKASA",
        "GON",
        "KILLUA",
        "HISOKA",
    ]

    # =====================================================
    # /DICE
    # =====================================================

    @app_commands.command(name="dice", description="Lance un dé.")
    @app_commands.describe(sides="Nombre de faces du dé")
    @channel_only(config.GAMES_CHANNEL_ID)
    async def dice(
        self,
        interaction: discord.Interaction,
        sides: app_commands.Range[int, 2, 100] = 6,
    ) -> None:

        result = random.randint(1, sides)

        embed = discord.Embed(
            title="🎲 Dice",
            description=(
                f"{interaction.user.mention} lance un "
                f"**D{sides}**...\n\n"
                f"🎯 Résultat : **{result}**"
            ),
            color=discord.Color.blue(),
        )

        await interaction.response.send_message(embed=embed)

    # =====================================================
    # /COINFLIP
    # =====================================================

    @app_commands.command(name="coinflip", description="Lance une pièce.")
    @channel_only(config.GAMES_CHANNEL_ID)
    async def coinflip(self, interaction: discord.Interaction) -> None:

        result = random.choice(
            [
                ("Pile", "🪙"),
                ("Face", "👑"),
            ]
        )

        name, emoji = result

        embed = discord.Embed(
            title="🪙 Coin Flip",
            description=(
                f"{interaction.user.mention} lance la pièce...\n\n"
                f"{emoji} **{name} !**"
            ),
            color=discord.Color.gold(),
        )

        await interaction.response.send_message(embed=embed)

    # =====================================================
    # /RPS
    # =====================================================

    @app_commands.command(name="rps", description="Joue à Pierre-Papier-Ciseaux.")
    @app_commands.describe(
        choice="Ton choix",
        user="Utilisateur à défier (vide = jouer contre le bot)",
    )
    @app_commands.choices(
        choice=[
            app_commands.Choice(
                name="🪨 Pierre",
                value="rock",
            ),
            app_commands.Choice(
                name="📄 Papier",
                value="paper",
            ),
            app_commands.Choice(
                name="✂️ Ciseaux",
                value="scissors",
            ),
        ]
    )
    @channel_only(config.GAMES_CHANNEL_ID)
    async def rps(
        self,
        interaction: discord.Interaction,
        choice: app_commands.Choice[str],
        user: discord.Member | None = None,
    ) -> None:

        # =====================================================
        # VS BOT
        # =====================================================

        if user is None:

            bot_choice = random.choice(
                [
                    "rock",
                    "paper",
                    "scissors",
                ]
            )

            emojis = {
                "rock": "🪨",
                "paper": "📄",
                "scissors": "✂️",
            }

            names = {
                "rock": "Pierre",
                "paper": "Papier",
                "scissors": "Ciseaux",
            }

            user_choice = choice.value

            if user_choice == bot_choice:

                result = "🤝 **Égalité !**"
                color = discord.Color.orange()

            elif (
                (user_choice == "rock" and bot_choice == "scissors")
                or (user_choice == "paper" and bot_choice == "rock")
                or (user_choice == "scissors" and bot_choice == "paper")
            ):

                result = f"🏆 {interaction.user.mention} " f"**a gagné !**"

                color = discord.Color.green()

            else:

                result = "🤖 **Le bot a gagné !**"
                color = discord.Color.red()

            embed = discord.Embed(
                title="⚔️ Pierre • Papier • Ciseaux",
                description=(f"{interaction.user.mention} " f"VS 🤖 **K.R.O.T.E**"),
                color=color,
            )

            embed.add_field(
                name=interaction.user.display_name,
                value=(f"{emojis[user_choice]} " f"**{names[user_choice]}**"),
                inline=True,
            )

            embed.add_field(
                name="K.R.O.T.E",
                value=(f"{emojis[bot_choice]} " f"**{names[bot_choice]}**"),
                inline=True,
            )

            embed.add_field(
                name="Résultat",
                value=result,
                inline=False,
            )

            await interaction.response.send_message(embed=embed)

            return

        # =====================================================
        # VS USER
        # =====================================================

        if user.id == interaction.user.id:

            await interaction.response.send_message(
                "❌ Tu ne peux pas te défier toi-même.",
                ephemeral=True,
            )

            return

        if user.bot:

            await interaction.response.send_message(
                "❌ Tu ne peux pas défier un autre bot. "
                "Laisse `user` vide pour jouer contre K.R.O.T.E.",
                ephemeral=True,
            )

            return

        if not isinstance(interaction.user, discord.Member):

            await interaction.response.send_message(
                "❌ Impossible de créer le duel.",
                ephemeral=True,
            )

            return

        # Le choix du challenger est enregistré,
        # mais surtout PAS affiché avant que l'autre joue.

        view = RPSChallengeView(
            challenger=interaction.user,
            opponent=user,
            challenger_choice=choice.value,
        )

        embed = discord.Embed(
            title="⚔️ Défi Pierre • Papier • Ciseaux",
            description=(
                f"{interaction.user.mention} défie "
                f"{user.mention} !\n\n"
                f"🔒 **{interaction.user.display_name} a déjà joué.**\n"
                f"⏳ {user.mention}, à toi de choisir !"
            ),
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="Adversaires",
            value=(f"{interaction.user.mention}\n" f"**VS**\n" f"{user.mention}"),
            inline=False,
        )

        embed.set_footer(text="Le défi expire dans 60 secondes.")

        await interaction.response.send_message(
            embed=embed,
            view=view,
        )

        view.message = await interaction.original_response()

    # =====================================================
    # HANGMAN
    # =====================================================

    @app_commands.command(name="hangman", description="Lance une partie de pendu.")
    @channel_only(config.GAMES_CHANNEL_ID)
    async def hangman(
        self,
        interaction: discord.Interaction,
    ) -> None:

        if not isinstance(
            interaction.user,
            discord.Member,
        ):
            await interaction.response.send_message(
                "❌ Impossible de lancer la partie.",
                ephemeral=True,
            )
            return

        channel_id = interaction.channel_id

        # Une seule partie par salon
        if channel_id in self.active_hangman_games:

            game = self.active_hangman_games[channel_id]

            if not game.finished:

                await interaction.response.send_message(
                    "❌ Une partie de Hangman " "est déjà en cours.",
                    ephemeral=True,
                )
            return

        word = random.choice(self.HANGMAN_WORDS)

        game = HangmanGame(
            word=word,
            started_by=interaction.user,
        )

        self.active_hangman_games[channel_id] = game

        embed = game.create_embed(
            "💬 Envoyez une **lettre** ou " "le **mot complet** dans le chat !"
        )

        await interaction.response.send_message(embed=embed)

        game.message = await interaction.original_response()

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message,
    ) -> None:

        # Bots ignorés
        if message.author.bot:
            return

        # DMs ignorés
        if message.guild is None:
            return

        # Uniquement le salon Games
        if message.channel.id != config.GAMES_CHANNEL_ID:
            return

        game = self.active_hangman_games.get(message.channel.id)

        # Pas de partie active :
        # on ne touche à aucun message.
        if game is None:
            return

        if game.finished:
            return

        guess = message.content.strip().upper()

        if not guess:
            return

        # On ne considère que les lettres/mots
        if not guess.isalpha():
            return

        # =====================================================
        # SUPPRESSION DU MESSAGE
        # =====================================================

        try:
            await message.delete()

        except discord.Forbidden:
            print(
                "⚠️ Impossible de supprimer le message Hangman : "
                "permission Manage Messages manquante."
            )

        except discord.HTTPException as error:
            print(f"⚠️ Erreur suppression message Hangman : {error}")

        # =====================================================
        # UNE LETTRE
        # =====================================================

        if len(guess) == 1:

            await self.process_hangman_letter(
                message,
                game,
                guess,
            )

            return

        # =====================================================
        # MOT COMPLET
        # =====================================================

        await self.process_hangman_word(
            message,
            game,
            guess,
        )

    async def process_hangman_letter(
        self,
        message: discord.Message,
        game: HangmanGame,
        letter: str,
    ) -> None:

        # Lettre déjà proposée
        if letter in game.guessed_letters or letter in game.wrong_letters:
            return

        # =====================================================
        # BONNE LETTRE
        # =====================================================

        if letter in game.word:

            game.guessed_letters.add(letter)

            # Partie gagnée
            if game.is_won():

                game.finished = True

                embed = game.create_embed(
                    f"🎉 {message.author.mention} "
                    f"a trouvé la dernière lettre !\n\n"
                    f"Le mot était **{game.word}**."
                )

                await game.message.edit(embed=embed)

                self.active_hangman_games.pop(
                    message.channel.id,
                    None,
                )

                return

            embed = game.create_embed(
                f"✅ {message.author.mention} " f"a trouvé **{letter}** !"
            )

            await game.message.edit(embed=embed)

            return

        # =====================================================
        # MAUVAISE LETTRE
        # =====================================================

        game.wrong_letters.add(letter)

        game.errors += 1

        # Perdu
        if game.errors >= game.MAX_ERRORS:

            game.finished = True

            embed = game.create_embed(
                f"💀 Plus aucun essai !\n\n" f"Le mot était **{game.word}**."
            )

            await game.message.edit(embed=embed)

            self.active_hangman_games.pop(
                message.channel.id,
                None,
            )

            return

        embed = game.create_embed(
            f"❌ {message.author.mention} : " f"**{letter}** n'est pas dans le mot."
        )

        await game.message.edit(embed=embed)

    async def process_hangman_word(
        self,
        message: discord.Message,
        game: HangmanGame,
        guess: str,
    ) -> None:

        # =====================================================
        # BON MOT
        # =====================================================

        if guess == game.word:

            for char in game.word:

                if char.isalpha():
                    game.guessed_letters.add(char)

            game.finished = True

            embed = game.create_embed(
                f"🏆 {message.author.mention} "
                f"a trouvé le mot complet : "
                f"**{game.word}** !"
            )

            await game.message.edit(embed=embed)

            self.active_hangman_games.pop(
                message.channel.id,
                None,
            )

            return

        # =====================================================
        # MAUVAIS MOT
        # =====================================================

        game.errors += 1

        if game.errors >= game.MAX_ERRORS:

            game.finished = True

            embed = game.create_embed(
                f"💀 {message.author.mention} "
                f"a proposé **{guess}**.\n"
                f"Ce n'était pas le bon mot.\n\n"
                f"Le mot était **{game.word}**."
            )

            await game.message.edit(embed=embed)

            self.active_hangman_games.pop(
                message.channel.id,
                None,
            )

            return

        embed = game.create_embed(
            f"❌ {message.author.mention} "
            f"a proposé **{guess}**.\n"
            f"Ce n'est pas le bon mot."
        )

        await game.message.edit(embed=embed)

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

        else:

            print("❌ Erreur Games : " f"{type(error).__name__}: {error}")

            message = (
                "❌ Une erreur est survenue pendant " "l'exécution de la commande."
            )

        try:

            if interaction.response.is_done():

                await interaction.followup.send(message, ephemeral=True)

            else:

                await interaction.response.send_message(message, ephemeral=True)

        except discord.NotFound:

            print("⚠️ Interaction Discord expirée.")


async def setup(bot: commands.Bot):
    await bot.add_cog(GamesCog(bot))
