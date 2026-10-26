import discord
from discord.ext import commands

import config
from database.database import Database

from events.messages import MessageEvents

from services.xp_service import XPService
from services.twitch_service import TwitchService

intents = discord.Intents.default()

intents.guilds = True
intents.members = True
intents.message_content = True
intents.voice_states = True
intents.presences = True


class DiscordBot(commands.Bot):

    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

        self.database = Database(config.DATABASE_URL)
        self.xp_service = XPService(
            database=self.database,
            guild_id=config.GUILD_ID,
            level_channel_id=config.LEVEL_CHANNEL_ID,
        )

        self.twitch_service = TwitchService(
            client_id=config.TWITCH_CLIENT_ID,
            client_secret=config.TWITCH_CLIENT_SECRET,
        )

        self.message_events = MessageEvents(self.xp_service)

    async def setup_hook(self):
        print("Initialisation du bot...")

        await self.database.connect()

        if await self.database.test_connection():
            print("✅ Test PostgreSQL réussi.")

        webtoons = await self.database.get_all_webtoons()
        gifs = await self.database.get_gifs()
        leaderboard = await self.database.get_leaderboard()
        commands_list = await self.database.get_all_commands()
        streamers = await self.database.get_all_streamers()

        print()
        print("===== DONNÉES EXISTANTES =====")
        print(f"📚 Webtoons : {len(webtoons)}")
        print(f"🎞️ GIFs     : {len(gifs)}")
        print(f"🏆 UserXP   : {len(leaderboard)}")
        print(f"⚙️ Commands : {len(commands_list)}")
        print(f"🟣 Streamers: {len(streamers)}")
        print("==============================")

        await self.load_extension("cogs.xp")
        await self.load_extension("cogs.gifs")
        await self.load_extension("cogs.webtoons")
        await self.load_extension("cogs.general")
        await self.load_extension("cogs.roles")
        await self.load_extension("cogs.polls")
        await self.load_extension("cogs.moderation")
        await self.load_extension("cogs.games")
        await self.load_extension("cogs.twitch")
        await self.load_extension("cogs.music")

        # Slash commands sur le serveur de développement
        guild = discord.Object(id=config.GUILD_ID)

        self.tree.copy_global_to(guild=guild)

        synced = await self.tree.sync(guild=guild)

        print(f"✅ {len(synced)} slash command(s) synchronisée(s).")

    async def on_message(self, message: discord.Message) -> None:
        await self.message_events.on_message(message)

        await self.process_commands(message)

    async def initialize_guild_users(self) -> None:
        guild = self.get_guild(config.GUILD_ID)

        if guild is None:
            print(f"⚠️ Serveur {config.GUILD_ID} " "introuvable.")
            return

        print(f"👥 Initialisation des membres " f"de {guild.name}...")

        count = 0

        for member in guild.members:

            if member.bot:
                continue

            await self.database.add_xp(member.id, member.display_name, 0)

            count += 1

        print(f"✅ {count} membres vérifiés " f"dans UserXP.")

    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        if member.guild.id != config.GUILD_ID:
            return

        await self.database.add_xp(member.id, member.display_name, 0)

        print(f"👤 {member.display_name} " "ajouté à UserXP.")

    async def close(self):
        await self.database.disconnect()
        await super().close()

    async def on_ready(self):
        if self.user is None:
            return

        print()
        print("================================")
        print(f"🤖 Connecté : {self.user}")
        print(f"🆔 ID       : {self.user.id}")
        print(f"🌐 Serveurs : {len(self.guilds)}")
        print("================================")

        await self.initialize_guild_users()

        guild = self.get_guild(config.GUILD_ID)

        if guild:
            member = guild.get_member(264151335132332032)

            if member:
                print("===== PRESENCE DEBUG =====")
                print(f"User     : {member}")
                print(f"Status   : {member.status}")
                print(f"Desktop  : {member.desktop_status}")
                print(f"Mobile   : {member.mobile_status}")
                print(f"Web      : {member.web_status}")
                print(f"Activity : {member.activity}")
                print("==========================")


bot = DiscordBot()

bot.run(config.DISCORD_TOKEN)
