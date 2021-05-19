import asyncio
import os
import signal
from asyncio import gather
from logging import getLogger
from pathlib import Path

from northisbot.lib.bot import Bot
from northisbot.lib.config import configure_logging

logger = getLogger(__name__)
configure_logging()


def bot_main():
    logger.info('starting bot')

    root = Path(__file__).parent
    bot = Bot('!', config_prefix='NORTHISBOT')
    bot.run(extension_roots=[root / 'northisbot'])

    logger.info('ending bot')


if __name__ == '__main__':
    bot_main()
