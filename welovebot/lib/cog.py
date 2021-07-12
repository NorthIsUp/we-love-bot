from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from functools import cached_property, wraps
from time import time
from typing import TYPE_CHECKING, Awaitable, Callable, List, Optional, Type, Union

from discord.ext import commands
from discord_slash import cog_ext
from redis import StrictRedis

from .config import BotConfig, ChainConfig, CogConfig
from .config import Config as BaseConfig
from .config import TypedChainConfig

if TYPE_CHECKING:
    from .bot import Bot

logger = logging.getLogger(__name__)


class BaseCog(commands.Cog):
    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """helper to access the bot event loop"""
        return self.bot.loop

    @classmethod
    def on_ready(cls, func):
        """decorator to run a function on the 'on_ready' event"""
        return cls.task(func, listener='on_ready')

    @classmethod
    def task(cls, func: Callable[[Cog], None], listener='on_ready'):
        @cls.listener(listener)
        @wraps(func)
        async def wrapper(self):
            self.debug(f'[on_ready] starting {func.__name__}')
            await self.loop.create_task(func(self))
            self.debug(f'[on_ready] complete {func.__name__}')

        return wrapper

    @classmethod
    def perodic_task(cls, seconds: int = 0, listener='on_ready'):
        def decorator(func: Callable[[Cog], Awaitable[None]]):
            @cls.listener('on_ready')
            @wraps(func)
            async def wrapper(self: Cog):
                async def _perodic_task() -> None:
                    name = f'{self.__class__.__name__}.{func.__name__}'
                    previous_duration = ''
                    while True:
                        try:
                            start = time()
                            self.debug(f'periodic - {name} - every {seconds}s{previous_duration}')
                            await func(self)
                            duration = time() - start

                            s, c = (
                                (1000000, 'µ')
                                if duration < 0.001
                                else (1000, 'm')
                                if duration < 0.1
                                else (1, '')
                            )
                            previous_duration = f' - previous duration: {duration * s:.2f}{c}s'

                        except Exception as e:
                            self.exception(e)
                        await asyncio.sleep(seconds)

                self.loop.create_task(_perodic_task())

            return wrapper

        return decorator

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
    bot: Bot

    class Config:
        pass

    @cached_property
    def name(self) -> str:
        return self.__class__.__name__

    @cached_property
    def config(self) -> BaseConfig:
        return ChainConfig((self.cog_config, self.bot_config))

    @cached_property
    def config_safe(self) -> TypedChainConfig:
        try:
            return TypedChainConfig((self.cog_config, self.bot_config), self.Config)
        except Exception as e:
            self.exception(e)
            raise

    @cached_property
    def cog_config(self) -> BaseConfig:
        return CogConfig(self.bot, self.__class__)

    @cached_property
    def bot_config(self) -> BaseConfig:
        return BotConfig(self.bot)

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

    def exception(self, msg: Union[str, Exception], *args, **kwargs) -> None:
        self.logger.exception(msg, *args, **kwargs)


@dataclass
class RedisCog(Cog):
    @cached_property
    def redis(self) -> StrictRedis:
        from redis import from_url

        return from_url(self.config['REDIS_URL'])

    @Cog.on_ready
    async def on_ready(self):
        self.bot.send
        self.redis.keys()
