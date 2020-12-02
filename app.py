import os
from northisbot.bot import NorthIsBot
from pathlib import Path

root = Path(__file__).parent

bot = NorthIsBot('!')
bot.discover_extensions(root / 'northisbot')
bot.run(os.environ["DISCORD_NORTHISBOT_TOKEN"])
