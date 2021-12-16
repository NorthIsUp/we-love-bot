import typing

import nextcord
from nextcord.ext import commands

from welovebot.lib.cog import Cog


class Moderation(Cog):
    @Cog.command()
    async def ban(
        ctx,
        members: commands.Greedy[nextcord.Member],
        delete_days: typing.Optional[int] = 0,
        *,
        reason: str,
    ):
        """Mass bans members with an optional delete_days parameter"""
        for member in members:
            await member.ban(delete_message_days=delete_days, reason=reason)
