import logging

from discord.ext import commands

logger = logging.getLogger(__name__)


@commands.command()
async def ping(ctx, arg):
    logger.info(f"ping {arg}")
    await ctx.send(arg)
