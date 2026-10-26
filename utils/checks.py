import discord
from discord import app_commands

import config


class MissingRequiredRole(app_commands.CheckFailure):
    pass


class WrongChannel(app_commands.CheckFailure):
    def __init__(self, channel_id: int):
        self.channel_id = channel_id

        super().__init__(f"Commande limitée au salon {channel_id}")


def has_required_role():
    async def predicate(interaction: discord.Interaction) -> bool:

        if not isinstance(interaction.user, discord.Member):
            raise MissingRequiredRole()

        user_role_ids = {role.id for role in interaction.user.roles}

        has_role = any(role_id in user_role_ids for role_id in config.REQUIRED_ROLE_IDS)

        if not has_role:
            raise MissingRequiredRole()

        return True

    return app_commands.check(predicate)


def channel_only(channel_id: int):
    async def predicate(interaction: discord.Interaction) -> bool:

        if interaction.channel_id != channel_id:
            raise WrongChannel(channel_id)

        return True

    return app_commands.check(predicate)
