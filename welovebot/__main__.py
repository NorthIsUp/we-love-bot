import sys
from argparse import ArgumentParser
from logging import getLogger
from os import environ
from pathlib import Path

logger = getLogger(__name__)

try:
    from rich import pretty, traceback

    traceback.install(show_locals=True)
    pretty.install()

    logger.info('using rich output')
except ImportError:
    logger.info('rich not available')

# fix the import path
welovebot_root = Path(__file__).parent
sys.path.insert(0, str(welovebot_root.parent))

# finish local imports
from welovebot import constants
from welovebot.lib.bot import Bot
from welovebot.lib.config import configure_logging


def parse_apps_env_var():
    apps_str = environ.get(constants.WELOVEBOT_APPS_ENVVAR, constants.WELOVEBOT_APPS_DEFAULT)
    apps_str = ','.join(apps_str.split())
    apps_str = apps_str.split(',')
    return [app.strip() for app in apps_str if app.strip()]


def parse_args():
    parser = ArgumentParser()
    print(parse_apps_env_var())
    parser.add_argument(
        '--app', dest='apps', nargs='*', action='extend', default=parse_apps_env_var()
    )
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
