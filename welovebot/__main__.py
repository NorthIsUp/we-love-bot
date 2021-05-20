import sys
from logging import getLogger
from pathlib import Path

# fix the import path
welovebot_root = Path(__file__).parent
sys.path.insert(0, str(welovebot_root.parent))

from welovebot.lib.bot import Bot
from welovebot.lib.config import configure_logging

logger = getLogger(__name__)

try:
    configure_logging()

    logger.info('starting bot')
    bot = Bot('!')
    bot.run(installed_apps=['welovebot.apps'])
except Exception as e:
    logger.exception(e)
finally:
    logger.info('ending bot')
