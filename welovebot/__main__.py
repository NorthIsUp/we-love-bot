import sys
from logging import getLogger
from pathlib import Path

# fix the import path
welovebot_root = Path(__file__).parent
sys.path.insert(0, str(welovebot_root.parent))
from argparse import ArgumentParser

from welovebot.lib.bot import Bot
from welovebot.lib.config import configure_logging

logger = getLogger(__name__)


def parse_args():
    parser = ArgumentParser()
    parser.add_argument('--app', dest='apps', nargs='*', action='store', default=['welovebot.apps'])
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        configure_logging()

        logger.info('starting bot')
        bot = Bot('!')
        bot.run(installed_apps=args.apps)
    except Exception as e:
        logger.exception(e)
    finally:
        logger.info('ending bot')


if __name__ == '__main__':
    main()
