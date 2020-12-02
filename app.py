import os, sys
from logging import getLogger
from pathlib import Path

from northisbot.bot import NorthIsBot
from northisbot.config import configure_logging

logger = getLogger(__name__)
root = Path(__file__).parent

configure_logging()

logger.info("starting bot")

bot = NorthIsBot("!")
bot.discover_extensions(root / "northisbot")


@bot.command()
async def ping(ctx, arg):
    await ctx.send(arg)


bot.run(os.environ["DISCORD_NORTHISBOT_TOKEN"])
