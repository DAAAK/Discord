import discord

from services.xp_service import XPService


class MessageEvents:
    def __init__(
        self,
        xp_service: XPService
    ):
        self.xp_service = xp_service

    async def on_message(
        self,
        message: discord.Message
    ) -> None:

        await self.xp_service.process_message(
            message
        )