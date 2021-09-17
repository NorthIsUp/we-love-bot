from __future__ import annotations

import asyncio
import io
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from functools import cached_property, wraps
from pathlib import Path
from time import time
from typing import (
    TYPE_CHECKING,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Set,
    Type,
    Union,
    cast,
)

import aiohttp
import discord
from discord.ext import commands
from discord_slash import cog_ext
from redis import StrictRedis

from welovebot.lib.config import JsonConfig

from .config import BotConfig, ChainConfig, CogConfig
from .config import Config as BaseConfig
from .config import EnvConfig, TypedChainConfig

if TYPE_CHECKING:
    from .bot import Bot

logger = logging.getLogger(__name__)

TaskCallableT = Callable[['Cog'], Awaitable[None]]


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
    def task(
        cls,
        func_or_listener: Union[str, TaskCallableT],
        *,
        listener: str = 'on_ready',
        filter: Optional[Callable[[...], bool]] = None,
        filter_method: Optional[Callable[[Cog, ...], bool]] = None,
    ) -> TaskCallableT:

        if isinstance(func_or_listener, str):
            listener = func_or_listener
        elif func_or_listener.__name__.startswith('on_'):
            listener = func_or_listener.__name__

        def decorator(func: TaskCallableT):
            @cls.listener(listener)
            @wraps(func)
            async def wrapper(self, *args, **kwargs):
                if filter and filter(*args, **kwargs) is False:
                    self.debug(f'skipping listener {listener}')
                    return
                if filter_method and filter_method(self, *args, **kwargs) is False:
                    self.debug(f'skipping listener {listener}')
                    return
                self.debug(f'[{listener}] starting {func.__name__}')
                await self.loop.create_task(func(self, *args, **kwargs))
                self.debug(f'[{listener}] complete {func.__name__}')

            return wrapper

        return decorator if isinstance(func_or_listener, str) else decorator(func_or_listener)

    @classmethod
    def perodic_task(
        cls,
        seconds: int = 0,
        *,
        weeks: int = 0,
        days: int = 0,
        hours: int = 0,
        minutes: int = 0,
        milliseconds: int = 0,
        listener='on_ready',
    ):
        interval = timedelta(
            weeks=weeks,
            days=days,
            hours=hours,
            minutes=minutes,
            seconds=seconds,
            milliseconds=milliseconds,
        ).total_seconds()

        def decorator(func: Callable[[Cog], Awaitable[None]]):
            @cls.listener(listener)
            @wraps(func)
            async def wrapper(self: Cog):
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

    @cached_property
    def name(self) -> str:
        return self.__class__.__name__

    @cached_property
    def config(self) -> BaseConfig:
        return ChainConfig((self.cog_config, self.bot_config))

    @cached_property
    def config_safe(self) -> TypedChainConfig:
        if not (Config := getattr(self, 'Config', None)):
            raise AttributeError(f"class '{self.name}' is miss a 'Config'")

        try:
            return TypedChainConfig(
                configs=(self.cog_config, self.bot_config),
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


@dataclass
class ImageHandlingCog(Cog):
    @dataclass
    class IncompleteHandling(RuntimeError):
        """failed to fully handle the image"""

        url: str

    class Config:
        CHANNEL: int
        DB_PATH: str
        EMAIL_FORWARDS: Set[str]
        EMAIL_FORWARDS_FROM_ADDR: str

    class HandlerType(Protocol):
        def __call__(self, url: str, file: io.BytesIO, caption: Optional[str] = None) -> None:
            ...

    handlers: List[HandlerType] = field(default_factory=list)

    def __post_init__(self):
        for handler in self.config_safe.get('HANDLERS', ['discord_channel']):
            self.handlers.append(getattr(self, f'_handle_{handler}'))

    @cached_property
    def db(self) -> JsonConfig:
        db = JsonConfig(self.config_safe.get('DB_PATH', '/tmp/tinybeans.json'))
        seen_default: Dict[str, float] = {}
        db.setdefault('seen', seen_default)
        return db

    @cached_property
    def channel(self) -> discord.abc.TextChannel:
        channel = self.bot.get_channel(self.config_safe['CHANNEL'])
        assert channel
        return cast(discord.TextChannel, channel)

    @contextmanager
    def seen(self, id: Union[str, int], update: bool = True) -> bool:
        id = str(id)
        seen = self.db['seen'].get(id, False)

        try:
            yield seen
        except ImageHandlingCog.IncompleteHandling:
            self.warning(f'incomplete processing {id}')
        else:
            if not seen:
                self.db.update_in('seen', {id: time()})

    async def fetch_url_as_file(self, url: str) -> io.BytesIO:
        async with aiohttp.ClientSession() as session, session.get(url) as resp:
            if resp.status != 200:
                await self.channel.send('Could not download file...')
                raise ImageHandlingCog.IncompleteHandling(url)
            return io.BytesIO(await resp.read())

    async def handle_image_url(self, url: str, caption: Optional[str] = None):
        with self.seen(url) as seen:
            if not seen:
                file = await self.fetch_url_as_file(url)

                for handler in self.handlers:
                    handler(caption=caption, file=file, url=url)

    async def _handle_discord_channel(
        self,
        url: str,
        file: io.BytesIO,
        caption: Optional[str] = None,
    ) -> None:
        self.info(f'posting file: {caption + " " if caption else ""}{url}')
        await self.channel.send(caption, file=discord.File(file, Path(url).name))
        await asyncio.sleep(0.01)

    async def _handle_meural_forward(
        self,
        url: str,
        file: io.BytesIO,
        caption: Optional[str] = None,
    ) -> None:
        """send the entry to a meural frame"""
        if file is None:
            return

    async def _handle_email_forward(
        self,
        url: str,
        file: io.BytesIO,
        caption: Optional[str] = None,
    ) -> None:
        if (
            url is None
            or file is None
            or not (apikey := self.config.get('SENDGRID_API_KEY', ''))
            or not (recipients := self.config_safe.get('EMAIL_FORWARDS', []))
            or not (from_addr := self.config_safe.get('EMAIL_FORWARDS_FROM_ADDR', ''))
        ):
            return

        from email.mime.image import MIMEImage
        from email.mime.multipart import MIMEMultipart

        from aiosmtplib import SMTP

        message = MIMEMultipart()
        message['From'] = from_addr
        message['Subject'] = 'Hello World!'
        message.attach(MIMEImage(file.getvalue()))

        self.info(f'forwarding to {recipients}')
        smtp_client = SMTP(hostname='smtp.sendgrid.net', port=587)

        await smtp_client.connect(username='apikey', password=apikey, start_tls=True)
        await smtp_client.send_message(message, recipients=recipients)
        await smtp_client.quit()
