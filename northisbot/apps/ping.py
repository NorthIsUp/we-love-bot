import imp
import logging

from discord.ext import commands
from discord_slash import SlashContext, cog_ext

from northisbot.lib.cog import Cog

logger = logging.getLogger(__name__)


class Ping(Cog):
    @cog_ext.cog_slash(name='ping')
    async def ping(self, ctx: SlashContext) -> None:
        await ctx.send(f'Pong! ({self.bot.latency * 1000}ms)')
