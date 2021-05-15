from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import cached_property, wraps
from typing import List, Optional, Type

from discord.ext import commands
from discord_slash import cog_ext

from northisbot.lib.config import CogConfig, Config

logger = logging.getLogger(__name__)


class BaseCog(commands.Cog):
    @classmethod
    def on_ready(cls, func):
        return cls.listener('on_ready')(func)

    @classmethod
    def on_ready_create_task(cls, func):
        @cls.listener('on_ready')
        @wraps(func)
        async def wrapper(self):
            self.bot.loop.create_task(func(self))

        return wrapper

    @classmethod
    def command(
        cls,
        *,
        name: Optional[str] = None,
        cmd_cls: Optional[Type[commands.Command]] = None,
        **attrs,
    ):
        def decorator(func):
            @commands.command(name=name, cls=cmd_cls, **attrs)
            @wraps(func)
            async def wrapper(self, *args, **kwargs):
                self.debug(f'handling command `{self.name}.{func.__name__}`')
                return await func(self, *args, **kwargs)

            return wrapper

        return decorator

    @classmethod
    def slash(
        cls,
        *,
        name: str = None,
        description: str = None,
        guild_ids: List[int] = None,
        options: List[dict] = None,
        connector: dict = None,
    ):
        def decorator(func):
            @cog_ext.cog_slash(
                name=name,
                description=description,
                guild_ids=guild_ids,
                options=options,
                connector=connector,
            )
            @wraps(func)
            def wrapper(self, *args, **kwargs):
                self.debug(f'handling slash command {func.__name__}')
                return func(self, *args, **kwargs)

            return wrapper

        return decorator

    @classmethod
    def slash_subcommand(
        cls,
        *,
        base,
        subcommand_group=None,
        name=None,
        description: str = None,
        base_description: str = None,
        base_desc: str = None,
        subcommand_group_description: str = None,
        sub_group_desc: str = None,
        guild_ids: List[int] = None,
        options: List[dict] = None,
        connector: dict = None,
    ):
        def decorator(func):
            @cog_ext.cog_subcommand(
                base=base,
                subcommand_group=subcommand_group,
                name=name,
                description=description,
                base_description=base_description,
                base_desc=base_desc,
                subcommand_group_description=subcommand_group_description,
                sub_group_desc=sub_group_desc,
                guild_ids=guild_ids,
                options=options,
                connector=connector,
            )
            @wraps(func)
            def wrapper(self, *args, **kwargs):
                self.debug(f'handling slash command {func.__name__}')
                return func(self, *args, **kwargs)

            return wrapper

        return decorator


@dataclass
class Cog(BaseCog):
    bot: commands.Bot

    @cached_property
    def name(self) -> str:
        return self.__class__.__name__

    @cached_property
    def config(self) -> Config:
        return CogConfig(self.bot, self.__class__)

    @cached_property
    def logger(self) -> logging.Logger:
        return logging.getLogger(self.__class__.__module__)

    def debug(self, msg: str, *args, **kwargs) -> None:
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self.logger.error(msg, *args, **kwargs)
