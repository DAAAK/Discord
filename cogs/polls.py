import discord
from discord import app_commands
from discord.ext import commands

import config

from utils.checks import (
    WrongChannel,
    MissingRequiredRole,
    has_required_role,
    channel_only,
)


class PollsCog(commands.Cog):

    EMOJIS = [
        "1️⃣",
        "2️⃣",
        "3️⃣",
        "4️⃣",
        "5️⃣",
        "6️⃣",
        "7️⃣",
        "8️⃣",
        "9️⃣",
        "🔟",
    ]

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="poll", description="Crée un sondage.")
    @app_commands.describe(
        question="Question du sondage",
        option1="Première réponse",
        option2="Deuxième réponse",
        option3="Troisième réponse",
        option4="Quatrième réponse",
        option5="Cinquième réponse",
    )
    @has_required_role()
    @channel_only(config.POLL_CHANNEL_ID)
    async def poll(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        option3: str | None = None,
        option4: str | None = None,
        option5: str | None = None,
    ) -> None:

        options = [
            option1,
            option2,
            option3,
            option4,
            option5,
        ]

        options = [option.strip() for option in options if option and option.strip()]

        question = question.strip()

        if not question:
            await interaction.response.send_message(
                "❌ La question ne peut pas être vide.", ephemeral=True
            )
            return

        description = "\n\n".join(
            f"{self.EMOJIS[index]}  **{option}**"
            for index, option in enumerate(options)
        )

        embed = discord.Embed(
            title=f"📊 {question}", description=description, color=discord.Color.blue()
        )

        embed.set_footer(text=f"Poll created by {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)

        message = await interaction.original_response()

        for index in range(len(options)):
            await message.add_reaction(self.EMOJIS[index])

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

            print("❌ Erreur Poll : " f"{type(error).__name__}: {error}")

            message = (
                "❌ Une erreur est survenue pendant " "l'exécution de la commande."
            )

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PollsCog(bot))
