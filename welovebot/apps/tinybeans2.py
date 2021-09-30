from __future__ import annotations

import io
from asyncio import Semaphore
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import cached_property
from pathlib import Path
from typing import AsyncGenerator, ClassVar, Optional, Sequence, Set, Union

import aiohttp
import asyncstdlib as a
import discord
from aiosmtplib import SMTP
from cachetools import LRUCache
from pytinybeans.pytinybeans import PyTinybeans, TinybeanChild, TinybeanEntry

from welovebot.lib.cog import Cog, CogConfigCheck
from welovebot.lib.cogs.email_images import ImageHandlingCog
from welovebot.lib.config import JsonConfig


@dataclass
class Tinybeans(Cog):
    tb: PyTinybeans = field(default_factory=PyTinybeans)
    check_config_safe: ClassVar[CogConfigCheck] = CogConfigCheck.RAISE

    class Config:
        LOGIN: str
        PASSWORD: str
        CHILDREN_IDS: Set[int]
        IMAGE_CHANNEL: int
        EMAIL_RECIPIENTS: Set[str]
        EMAIL_FROM_ADDR: str
        INTERVAL: int

    @cached_property
    def last_sumthing(self) -> datetime:
        return datetime.utcnow() - timedelta(days=15)

    @a.cached_property
    async def children(self) -> Sequence[TinybeanChild]:
        ids = set(int(c) for c in self.config_safe['CHILDREN_IDS'])
        return tuple(c for c in await self.tb.children if c.id in ids)

    async def login(self) -> bool:
        self.info(f'Logging in... (currently logged in? {self.tb.logged_in})')
        await self.tb.login(self.config_safe['LOGIN'], self.config_safe['PASSWORD'])
        return self.tb.logged_in

    async def entries(self) -> AsyncGenerator[TinybeanEntry, None]:
        for c in await self.children:
            async for entry in self.tb.get_entries(c, limit=self.last_sumthing):
                yield entry

    @Cog.task('on_ready')
    async def _login_on_startup(self):
        await self.login()
        self.dispatch('tinybeans_login')

    @Cog.perodic_task(listener='on_tinybeans_login', minutes='INTERVAL=15')
    async def periodic_sync(self) -> None:
        async for entry in self.entries():
            self.info(f'handling entry: {entry.id}')
            self.dispatch('image_with_caption', source=self, url=entry.url, caption=entry.caption)


@dataclass
class ImageHandler(Cog):
    check_config_safe: ClassVar[CogConfigCheck] = CogConfigCheck.RAISE
    _lock: Semaphore = field(default_factory=Semaphore)
    _cache: LRUCache[str, io.BytesIO] = field(
        default_factory=lambda: LRUCache[str, io.BytesIO](128)
    )

    class Config:
        SENDGRID_API_KEY: str
        DB_PATH: str

    @cached_property
    def db(self) -> JsonConfig:
        return JsonConfig(self.config_safe.get('DB_PATH', '/tmp/tinybeans.json'))

    @contextmanager
    def seen(self, key: str, id: Union[int, str]) -> float:
        with self.db:
            seen_db = self.db.setdefault('seen', {}).setdefault(key, {})
            seen: bool = seen_db.get(id, False)

            if not seen:
                seen_db[id] = datetime.utcnow().isoformat()

            try:
                yield seen
            except Exception as e:
                seen_db[id] = False
                self.exception(e)

    async def fetch_url_as_file(self, url: str) -> io.BytesIO:
        if url not in self._cache:
            async with self._lock, aiohttp.ClientSession() as session, session.get(url) as resp:
                if resp.status != 200:
                    raise ImageHandlingCog.IncompleteHandling(url)
                self._cache[url] = io.BytesIO(await resp.read())

        return self._cache[url]

    @Cog.task('on_image_with_caption')
    async def _handle_discord_channel(
        self,
        source: Cog,
        url: str,
        caption: Optional[str] = None,
    ) -> None:

        with self.seen('discord_channel', url) as seen:
            if seen:
                return

            if not (channel := source.config_safe.get('IMAGE_CHANNEL')):
                return self.info('no channel to post image to')

            if not (file := await self.fetch_url_as_file(url)):
                return self.info('invalid image for discord send')

            self.info(f'posting file: {caption + " " if caption else ""}{url}')
            await self.bot.get_channel(channel).send(
                caption, file=discord.File(file, Path(url).name)
            )

    @a.cached_property
    async def _smtp_client(self) -> SMTP:
        apikey = self.config_safe['SENDGRID_API_KEY']
        smtp_client = SMTP(hostname='smtp.sendgrid.net', port=587)
        await smtp_client.connect(username='apikey', password=apikey, start_tls=True)
        return smtp_client

    @Cog.task('on_image_with_caption')
    async def handle_email_forward(
        self,
        source: Cog,
        url: str,
        caption: Optional[str] = None,
    ) -> None:
        if not (email_recipients := source.config_safe['EMAIL_RECIPIENTS']):
            return self.error('recipients missing')

        if not (email_from_addr := source.config_safe['EMAIL_FROM_ADDR']):
            return self.error('from addr missing')

        with self.seen('email_forward', url) as seen:
            if seen:
                return

            if not (file := await self.fetch_url_as_file(url)):
                return self.info('invalid image for email send')

            from email.mime.image import MIMEImage
            from email.mime.multipart import MIMEMultipart

            message = MIMEMultipart()
            message['From'] = email_from_addr
            message['Subject'] = caption or 'Hello World!'
            message.attach(MIMEImage(file.getvalue()))

            self.info(f'forwarding to {email_recipients}')
            client = await self._smtp_client
            await client.send_message(message, recipients=email_recipients)
