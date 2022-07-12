from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from functools import cached_property, wraps
from time import time
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    ClassVar,
    Coroutine,
    Dict,
    List,
    Optional,
    Type,
    Union,
)
from uuid import uuid4

from nextcord.ext import commands

# from discord_slash import cog_ext
from redis import StrictRedis

from .config import BotConfig, ChainConfig, CogConfig
from .config import Config as BaseConfig
from .config import EnvConfig, TypedChainConfig

if TYPE_CHECKING:
    from .bot import Bot

logger = logging.getLogger(__name__)

TaskCallableT = Callable[..., Awaitable[None]]


class BaseCog(commands.Cog):
    @cached_property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def enabled(self) -> bool:
        return self.config.get('ENABLED', True)

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """helper to access the bot event loop"""
        return self.bot.loop

    @classmethod
    def on_ready(cls, func: Callable[..., Any]):
        """decorator to run a function on the 'on_ready' event"""
        if not asyncio.iscoroutinefunction(func):
            raise SyntaxError(
                f"'{func.__module__}.{func.__name__}' is not a coroutine, try making it async"
            )
        return cls.task(func, listener='on_ready')

    @classmethod
    def task(
        cls,
        func_or_listener: Union[str, Coroutine[Any, Any, None]],
        *,
        listener: str = 'on_ready',
        filter: Optional[Callable[..., bool]] = None,
        filter_method: Optional[Callable[..., bool]] = None,
    ) -> TaskCallableT:

        if isinstance(func_or_listener, str):
            listener = func_or_listener
        elif func_or_listener.__name__.startswith('on_'):
            listener = func_or_listener.__name__

        def decorator(func: Coroutine[Any, Any, None]) -> Callable[..., None]:
            @cls.listener(listener)
            @wraps(func)
            async def wrapper(self: BaseCog, *args: Any, **kwargs: Any) -> None:
                if not self.enabled:
                    return cls.debug(f'[{func.__name__}:{listener}] disabled')
                elif filter and filter(*args, **kwargs) is False:
                    return cls.debug(f'[{func.__name__}:{listener}] filtered (unbound)')
                elif filter_method and filter_method(self, *args, **kwargs) is False:
                    return cls.debug(f'[{func.__name__}:{listener}] filtered (method)')

                @wraps(func)
                async def logging_func(self: BaseCog, *args: Any, **kwargs: Any) -> None:
                    uuid = uuid4()
                    cls.debug(f'[{listener}-{func.__name__}] starting {uuid}')
                    await func(self, *args, **kwargs)
                    cls.debug(f'[{listener}-{func.__name__}] complete {uuid}')

                cls.debug(f'[{listener}-{func.__name__}] scheduling')
                await self.loop.create_task(logging_func(self, *args, **kwargs))

            return wrapper

        return decorator if isinstance(func_or_listener, str) else decorator(func_or_listener)

    @classmethod
    def perodic_task(
        cls,
        seconds: Union[int, str] = 0,
        *,
        weeks: Union[int, str] = 0,
        days: Union[int, str] = 0,
        hours: Union[int, str] = 0,
        minutes: Union[int, str] = 0,
        milliseconds: Union[int, str] = 0,
        listener: str = 'on_ready',
    ):
        def decorator(func: Callable[[Cog], Awaitable[None]]):
            @cls.listener(listener)
            @wraps(func)
            async def wrapper(self: Cog):
                def int_or_config(s: Union[str, int]) -> int:
                    """use the passed int or check if the value is in config.
                    A default value can be passed via ENVVAR=default"""
                    if isinstance(s, int):
                        return s

                    envvar, *default = s.split('=')
                    return int(self.config_safe.get(envvar, default[0] if default else 0))

                interval = timedelta(
                    weeks=int_or_config(weeks),
                    days=int_or_config(days),
                    hours=int_or_config(hours),
                    minutes=int_or_config(minutes),
                    seconds=int_or_config(seconds),
                    milliseconds=int_or_config(milliseconds),
                ).total_seconds()

                async def _perodic_task() -> None:
                    name = f'{self.__class__.__name__}.{func.__name__}'
                    previous_duration = ''

                    while True:
                        try:
                            start = time()
                            self.debug(f'periodic - {name} - every {interval}s{previous_duration}')
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
                        await asyncio.sleep(interval)

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
                cls.debug(f'handling command `{self.name}.{func.__name__}`')
                return await func(self, *args, **kwargs)

            return wrapper

        return decorator

    # @classmethod
    # def slash(
    #     cls,
    #     *,
    #     name: str = None,
    #     description: str = None,
    #     guild_ids: List[int] = None,
    #     options: List[dict] = None,
    #     connector: dict = None,
    # ):
    #     def decorator(func):
    #         @cog_ext.cog_slash(
    #             name=name,
    #             description=description,
    #             guild_ids=guild_ids,
    #             options=options,
    #             connector=connector,
    #         )
    #         @wraps(func)
    #         def wrapper(self, *args, **kwargs):
    #             cls.debug(f'handling slash command {func.__name__}')
    #             return func(self, *args, **kwargs)

    #         return wrapper

    #     return decorator

    @classmethod
    def slash_subcommand(
        cls,
        *,
        base: str,
        subcommand_group: str = None,
        name: str = None,
        description: str = None,
        base_description: str = None,
        base_desc: str = None,
        subcommand_group_description: str = None,
        sub_group_desc: str = None,
        guild_ids: List[int] = None,
        options: List[Dict[str, object]] = None,
        connector: Dict[str, object] = None,
    ) -> Callable[..., object]:
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
                cls.debug(f'handling slash command {func.__name__}')
                return func(self, *args, **kwargs)

            return wrapper

        return decorator

    @classmethod
    def _logger(cls) -> logging.Logger:
        cls.logger = getattr(cls, 'logger', None) or logging.getLogger(cls.__module__)
        return cls.logger

    @classmethod
    def debug(cls, msg: str, *args: Any, **kwargs: Any) -> None:
        cls._logger().debug(msg, *args, **kwargs)

    @classmethod
    def info(cls, msg: str, *args: Any, **kwargs: Any) -> None:
        cls._logger().info(msg, *args, **kwargs)

    @classmethod
    def warning(cls, msg: str, *args: Any, **kwargs: Any) -> None:
        cls._logger().warning(msg, *args, **kwargs)

    @classmethod
    def error(cls, msg: str, *args: Any, **kwargs: Any) -> None:
        cls._logger().error(msg, *args, **kwargs)

    @classmethod
    def exception(cls, msg: Union[str, BaseException], *args: Any, **kwargs: Any) -> None:
        cls._logger().exception(msg, *args, **kwargs)


class CogConfigCheck(int, Enum):
    NO = False
    YES = True
    RAISE = 2

    def __bool__(self) -> bool:
        return self.value in (self.YES, self.RAISE)


@dataclass(unsafe_hash=True)
class Cog(BaseCog):
    bot: Bot
    check_config_safe: ClassVar[CogConfigCheck] = CogConfigCheck.NO

    @BaseCog.on_ready
    async def _check_config_safe(self) -> None:
        if self.check_config_safe is CogConfigCheck.NO:
            return

        # side effect ensures config types exist
        self.config_safe

        config = getattr(self, 'Config')
        tombstone = object()
        should_raise = []

        for key in config.__annotations__.keys():
            if self.config_safe.get(key, tombstone) is not tombstone:
                self.info(f'[  OK  ] {key} is present')
            elif self.check_config_safe is CogConfigCheck.YES:
                self.warning(f'[ WARN ] {key} is missing')
            elif self.check_config_safe is CogConfigCheck.RAISE:
                self.error(f'[ FAIL ] {key} is missing')
                should_raise.append(key)

        if should_raise:
            raise RuntimeError(f'missing config ({",".join(should_raise)})')

    @cached_property
    def config(self) -> ChainConfig:
        configs = [
            CogConfig(self.bot, cls) for cls in self.__class__.__mro__ if hasattr(cls, 'Config')
        ]

        return ChainConfig((*configs, self.bot_config))

    @cached_property
    def config_safe(self) -> TypedChainConfig:
        if not (Config := getattr(self, 'Config', None)):
            raise AttributeError(f"class '{self.name}' is missing a 'Config'")

        try:
            return TypedChainConfig(
                configs=self.config.configs,
                types=Config,
            )
        except Exception as e:
            self.exception(e)
            raise

    @cached_property
    def config_raw(self) -> EnvConfig:
        return self.bot.config

    @cached_property
    def cog_config(self) -> BaseConfig:
        return CogConfig(self.bot, self.__class__)

    @cached_property
    def bot_config(self) -> BaseConfig:
        return BotConfig(self.bot)

    def dispatch(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        self.bot.dispatch(event_name, *args, **kwargs)


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
