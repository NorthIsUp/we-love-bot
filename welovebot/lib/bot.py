from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from functools import cached_property
from logging import Logger, getLogger
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, List, Optional, Sequence, Union

import nextcord
from nextcord.ext import commands

# from discord_slash import SlashCommand

if TYPE_CHECKING:
    from .config import Config

logger = getLogger(__name__)


@dataclass(unsafe_hash=True)
class Bot(commands.Bot):
    def __init__(
        self,
        *args,
        config_prefix: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.config_prefix = config_prefix or self.config.prefix

    @cached_property
    def config(self) -> Config:
        """config for the bot, accessable via __getitem__ or get(key, default)"""
        from .config import BotConfig

        return BotConfig(self)

    @cached_property
    def config_env(self) -> Config:
        """config for the bot, accessable via __getitem__ or get(key, default)"""

    # @cached_property
    # def slash(self) -> SlashCommand:
    #     """use as a decorator to mark functions as slash commands"""
    #     return SlashCommand(
    #         self,
    #         application_id=self.application_id,
    #         sync_commands=True,
    #         override_type=True,
    #     )

    def discover_extensions(self, *paths_or_mods: Union[Path, str]):
        """load all cogs under path"""
        mods: List[ModuleType] = []

        for path_or_mod in paths_or_mods:
            try:
                mod = importlib.import_module(str(path_or_mod))
                mods.append(mod)
            except ImportError:
                path = Path(path_or_mod)
                logger.info(f'loading extensions from path: {path}')

                if not path.exists():
                    raise RuntimeError(f"path '{path}' does not exist")

                logger.debug(f'itermod {path} {list(pkgutil.iter_modules([str(path)]))}')
                for (module_loader, name, _ispkg) in pkgutil.iter_modules([str(path)]):
                    sub_loader = module_loader.find_module(name)
                    if sub_loader:
                        mod = sub_loader.load_module(name)
                        mods.append(mod)

        for mod in mods:
            logger.info(f'loading extensions from {mod.__name__} at {mod.__file__}')
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
            if getattr(loadable, 'enabled', True):
                logger.info(
                    f'- discovred Cog instance {loadable.__class__.__name__}@{repr(loadable)}'
                )
                self.add_cog(loadable)
            else:
                logger.info(
                    f'- disabled Cog instance {loadable.__class__.__name__}@{repr(loadable)}'
                )
        elif isinstance(loadable, type) and issubclass(loadable, commands.Cog):
            loadable_instance = loadable(self)
            if getattr(loadable_instance, 'enabled', True):
                logger.info(f'- discovred Cog class {loadable.__name__}@{repr(loadable)}')
                self.add_cog(loadable_instance)
            else:
                logger.info(f'- disabled Cog class {loadable.__name__}@{repr(loadable)}')
        elif isinstance(loadable, commands.Command):
            logger.info(f'- discovred Command {loadable}@{repr(loadable)}')
            self.add_command(loadable)
        elif isinstance(loadable, (int, str, bool, tuple, list)):
            pass
        else:
            logger.debug(f'- falling back to `load_extension({name})`')
            self.load_extension(name)

    async def on_ready(self) -> None:
        logger.debug('Logged on as {0}!'.format(self.user))

    async def send_message(self, message: nextcord.Message, response: str, img_url: str = None):
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
        installed_apps: Sequence[str] = (),
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.discover_extensions(*installed_apps)
        self.dispatch('run')
        super().run(token or self.config['DISCORD_TOKEN'], *args, **kwargs)
