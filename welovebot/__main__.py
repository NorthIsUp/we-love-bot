import os
from logging import getLogger
from pathlib import Path

from lib.bot import Bot
from lib.config import EnvConfig, configure_logging

root = Path(__file__).parent
logger = getLogger(__name__)

try:
    configure_logging()

    logger.info('starting bot')
    bot = Bot('!')
    bot.run(extension_roots=[root / 'easybot'])
except Exception as e:
    logger.exception(e)
finally:
    logger.info('ending bot')
