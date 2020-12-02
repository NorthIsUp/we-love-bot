import os, sys
from logging import getLogger
from pathlib import Path

from northisbot import bot
from northisbot.bot import NorthIsBot
from northisbot.config import configure_logging

logger = getLogger(__name__)
root = Path(__file__).parent

configure_logging()

logger.info("starting bot")

bot = NorthIsBot("!")
bot.discover_extensions(root / "northisbot")
bot.run(os.environ["DISCORD_NORTHISBOT_TOKEN"])
