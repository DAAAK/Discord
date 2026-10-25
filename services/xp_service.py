from datetime import datetime, timedelta, timezone

import discord

from database.database import Database


class XPService:
    XP_PER_MESSAGE = 5
    COOLDOWN = timedelta(minutes=2)

    def __init__(
        self,
        database: Database,
        guild_id: int,
        level_channel_id: int
    ):
        self.database = database
        self.guild_id = guild_id
        self.level_channel_id = level_channel_id

        self.cooldowns: dict[int, datetime] = {}

    async def process_message(
        self,
        message: discord.Message
    ) -> None:

        # Exactement comme le C# : pas d'XP aux bots
        if message.author.bot:
            return

        # Uniquement les messages envoyés dans un serveur
        if message.guild is None:
            return

        # Uniquement ton serveur
        if message.guild.id != self.guild_id:
            return

        user_id = message.author.id
        now = datetime.now(timezone.utc)

        # Cooldown de 2 minutes
        last_xp_time = self.cooldowns.get(user_id)

        if last_xp_time is not None:
            if now - last_xp_time < self.COOLDOWN:
                return

        # Comme dans ton C# :
        # le cooldown est enregistré AVANT l'ajout BDD
        self.cooldowns[user_id] = now

        display_name = (
            message.author.display_name
            if isinstance(message.author, discord.Member)
            else message.author.name
        )

        leveled_up, new_level, new_xp = (
            await self.database.add_xp(
                user_id,
                display_name,
                self.XP_PER_MESSAGE
            )
        )

        print(
            f"⭐ {display_name} +{self.XP_PER_MESSAGE} XP "
            f"→ {new_xp} XP | Level {new_level}"
        )

        if leveled_up:
            await self.send_level_up(
                message.author,
                new_level,
                new_xp
            )

    async def send_level_up(
        self,
        user: discord.abc.User,
        level: int,
        xp: int
    ) -> None:

        guild = user.guild if isinstance(
            user,
            discord.Member
        ) else None

        if guild is None:
            return

        channel = guild.get_channel(
            self.level_channel_id
        )

        if not isinstance(
            channel,
            discord.TextChannel
        ):
            print(
                "⚠️ Level channel introuvable : "
                f"{self.level_channel_id}"
            )
            return

        embed = discord.Embed(
            title="🎉 Level Up!",
            description=(
                f"{user.mention} has reached "
                f"**Level {level}**!"
            ),
            color=discord.Color.gold()
        )

        embed.set_thumbnail(
            url=user.display_avatar.url
        )

        embed.set_footer(
            text=f"XP: {xp}"
        )

        await channel.send(embed=embed)