import asyncio
import os
import signal
from asyncio import gather
from logging import getLogger
from pathlib import Path

from northisbot.bot import NorthIsBot
from northisbot.config import configure_logging

logger = getLogger(__name__)
configure_logging()

def bot_main():
    logger.info("starting bot")

    root = Path(__file__).parent
    bot = NorthIsBot("!")

    bot.discover_extensions(root / "northisbot")
    bot.run(os.environ["DISCORD_NORTHISBOT_TOKEN"])

    logger.info("ending bot")

if __name__ == '__main__':
    bot_main()
