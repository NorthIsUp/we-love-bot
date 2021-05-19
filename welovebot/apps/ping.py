import logging

from discord_slash import SlashContext

from welovebot.lib.cog import Cog

logger = logging.getLogger(__name__)


class Ping(Cog):
    @Cog.slash(name='ping')
    async def ping(self, ctx: SlashContext) -> None:
        await ctx.send(f'Pong! ({self.bot.latency * 1000}ms)')
