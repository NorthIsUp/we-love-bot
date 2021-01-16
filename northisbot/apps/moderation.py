import typing

import discord
from discord.ext import commands


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ban(
        ctx,
        members: commands.Greedy[discord.Member],
        delete_days: typing.Optional[int] = 0,
        *,
        reason: str
    ):
        """Mass bans members with an optional delete_days parameter"""
        for member in members:
            await member.ban(delete_message_days=delete_days, reason=reason)
