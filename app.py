try:
    import os, sys
    from logging import getLogger
    from pathlib import Path

    from os.path import dirname, basename, isfile, join
    import glob

    print("from", dirname(__file__))
    modules = glob.glob(join(dirname(__file__), "*.py"))
    __all__ = [
        basename(f)[:-3] for f in modules if isfile(f) and not f.endswith("__init__.py")
    ]
    print(__all__)

    from . import northisbot
    from northisbot import bot
    from northisbot.bot import NorthIsBot
    from northisbot.config import configure_logging

except ImportError as e:
    print(e)
    print(sys.path)
    raise
root = Path(__file__).parent

logger = getLogger(__name__)


configure_logging()

logger.info("starting bot")

bot = NorthIsBot("!")
bot.discover_extensions(root / "northisbot")
bot.run(os.environ["DISCORD_NORTHISBOT_TOKEN"])
