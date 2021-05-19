from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from functools import cached_property

from logging import Logger, getLogger
from pathlib import Path
from types import ModuleType
from typing import (TYPE_CHECKING,
 Optional, Sequence, Union)

import discord
from discord.ext import commands
from discord_slash import SlashCommand

if TYPE_CHECKING:
    from .config import Config

logger = getLogger(__name__)


@dataclass
class Bot(commands.Bot):
    def __init__(
        self,
        *args,
        application_id: Optional[str] = None,
        config_prefix: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.config_prefix = config_prefix
        self.application_id = self.config.get('APPLICATION_ID', application_id)

    @cached_property
    def config(self) -> Config:
        """config for the bot, accessable via __getitem__ or get(key, default)"""
        from .config import BotConfig

        return BotConfig(self)

    @cached_property
    def slash(self) -> SlashCommand:
        """use as a decorator to mark functions as slash commands"""
        return SlashCommand(
            self, application_id=self.application_id, sync_commands=True, override_type=True,
        )

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

    async def on_ready(self) -> None:
        logger.debug('Logged on as {0}!'.format(self.user))

    async def send_message(self, message: discord.Message, response: str, img_url: str = None):
        """helper for sending messages in a channel with a typing indicator"""
        for small_response in (r.strip() for r in response.split('\n\n') if r.strip()):
            await message.channel.trigger_typing()
            await message.channel.send(small_response)
        if img_url:
            await message.channel.trigger_typing()
            await message.channel.send(img_url)

    def run(
        self,
        # the bot token
        token: Optional[str] = None,
        # is this a bot, yes, yes it is
        bot: bool = True,
        # roots to search for cogs and other extensions
        extension_roots: Sequence[Path] = (),
    ) -> None:
        for root in extension_roots:
            self.discover_extensions(root)

        super().run(token or self.config['DISCORD_TOKEN'], bot=bot)
