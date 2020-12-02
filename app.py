import os
from logging import getLogger
from pathlib import Path

from northisbot.bot import NorthIsBot
from northisbot.config import configure_logging

logger = getLogger(__name__)


configure_logging()

logger.info("starting bot")
root = Path(__file__).parent

bot = NorthIsBot("!")
bot.discover_extensions(root / "northisbot")
bot.run(os.environ["DISCORD_NORTHISBOT_TOKEN"])
