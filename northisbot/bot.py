import asyncio
import importlib
import pkgutil
from abc import ABC, ABCMeta
from logging import Logger, getLogger
from pathlib import Path
from types import ModuleType
from typing import Union

import discord
from discord.ext import commands
from discord_slash import SlashCommand

from northisbot.lib.config import BotConfig

logger = getLogger(__name__)


class NorthIsBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.application_id = BotConfig(self.__class__).get('APPLICATION_ID', None)
        self.slash = SlashCommand(
            self, application_id=self.application_id, sync_commands=True, override_type=True
        )

    async def on_ready(self) -> None:
        logger.debug('Logged on as {0}!'.format(self.user))

    def discover_extensions(self, path: Union[Path, str]):
        """load all cogs under path"""
        path = Path(path)

        logger.info('loading extensions')
        for location in [path / 'apps']:
            if not location.exists():
                continue

            for (module_loader, name, ispkg) in pkgutil.iter_modules([str(location)]):
                mod = importlib.import_module(f'{path.name}.{location.name}.{name}')
                for name in dir(mod):
                    self.discover_extension(name, mod)

    def discover_extension(self, name: str, mod: ModuleType) -> None:
        """attempt to load an extension from a module"""
        loadable = getattr(mod, name, None)
        if (
            name.startswith('_')
            or isinstance(loadable, (ModuleType, Logger))
            # ignore modules imported from elsewhere
            or (hasattr(loadable, '__module__') and loadable.__module__ != mod.__name__)
        ):
            pass
        elif isinstance(loadable, commands.Cog):
            logger.info(f'- discovred Cog instance {loadable.__name__}.@{repr(loadable)}')
            self.add_cog(loadable)
        elif isinstance(loadable, type) and issubclass(loadable, commands.Cog):
            logger.info(f'- discovred Cog class {loadable.__name__}@{repr(loadable)}')
            self.add_cog(loadable(self))
        elif isinstance(loadable, commands.Command):
            logger.info(f'- discovred Command {loadable}@{repr(loadable)}')
            self.add_command(loadable)
        else:
            logger.debug(f'- falling back to `load_extension({name})`')
            self.load_extension(name)

    async def send_message(self, message: discord.Message, response: str, img_url: str = None):
        for small_response in (r.strip() for r in response.split('\n\n') if r.strip()):
            await message.channel.trigger_typing()
            await message.channel.send(small_response)
        if img_url:
            await message.channel.trigger_typing()
            await message.channel.send(img_url)
