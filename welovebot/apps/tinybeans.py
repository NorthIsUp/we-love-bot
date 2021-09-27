from __future__ import annotations

import asyncio
import io
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import cached_property
from pathlib import Path
from time import time
from typing import AsyncGenerator, ClassVar, Dict, Optional, Sequence, Set, Union

import aiohttp
import asyncstdlib as a
import discord
from aiosmtplib import SMTP
from pytinybeans.pytinybeans import PyTinybeans, TinybeanChild, TinybeanEntry

from welovebot.lib.cog import Cog, CogConfigCheck
from welovebot.lib.config import JsonConfig


@dataclass
class Tinybeans(Cog):
    tb: PyTinybeans = field(default_factory=PyTinybeans)
    check_config_safe: ClassVar[CogConfigCheck] = CogConfigCheck.RAISE

    class Config:
        LOGIN: str
        PASSWORD: str
        CHILDREN_IDS: Set[int]
        CHANNEL: int
        DB_PATH: str
        EMAIL_FORWARDS: Set[str]
        EMAIL_FORWARDS_FROM_ADDR: str
        SENDGRID_API_KEY: str

    @cached_property
    def db(self) -> JsonConfig:
        db = JsonConfig(self.config_safe.get('DB_PATH', '/tmp/tinybeans.json'))
        seen_default: Dict[str, float] = {}
        db.setdefault('seen', seen_default)
        return db

    @cached_property
    def last_sumthing(self) -> datetime:
        return datetime.utcnow() - timedelta(days=15)

    @cached_property
    def channel(self) -> discord.TextChannel:
        return self.bot.get_channel(self.config_safe['CHANNEL'])

    async def login(self) -> bool:
        self.info(f'Logging in... (currently logged in? {self.tb.logged_in})')
        await self.tb.login(self.config_safe['LOGIN'], self.config_safe['PASSWORD'])
        return self.tb.logged_in

    @a.cached_property
    async def children(self) -> Sequence[TinybeanChild]:
        ids = set(int(c) for c in self.config_safe['CHILDREN_IDS'])
        return tuple(c for c in await self.tb.children if c.id in ids)

    async def entries(self) -> AsyncGenerator[TinybeanEntry, None]:
        for c in await self.children:
            async for entry in self.tb.get_entries(c, limit=self.last_sumthing):
                yield entry

    @Cog.perodic_task(minutes=int(os.environ.get('TINYBEANS_INTERVAL', 15)))
    async def periodic_sync(self) -> None:
        logged_in = await self.login()
        self.debug(f'login success? {logged_in}')
        await self.handle_entries(self.entries())

    def seen(self, id: Union[str, int], update: bool = True) -> bool:
        id = str(id)
        seen: bool = self.db['seen'].get(id, False)

        if not seen:
            self.db.update_in('seen', {id: time()})

        return seen

    async def fetch_url_as_file(self, url: str) -> io.BytesIO:
        async with aiohttp.ClientSession() as session, session.get(url) as resp:
            if resp.status != 200:
                await self.channel.send('Could not download file...')
                raise RuntimeError(f'Could not download file at {url}')
            return io.BytesIO(await resp.read())

    async def handle_entries(
        self,
        entries: AsyncGenerator[TinybeanEntry, None],
    ) -> None:
        async for entry in entries:
            if not self.seen(entry.id):
                self.info(f'handling entry: {entry.id}')
                file = None
                if not entry.is_text:
                    file = await self.fetch_url_as_file(entry.url)

                await asyncio.gather(
                    self.handle_discord_send(entry, file),
                    self.handle_email_forward(entry, file),
                )

    async def handle_discord_send(
        self,
        entry: TinybeanEntry,
        file: Optional[io.BytesIO] = None,
    ) -> None:
        if entry.is_text:
            self.info(f'posting text: {entry.caption}')
            await self.channel.send(entry.caption)
        elif file is not None:
            self.info(f'posting file: {entry.caption + " " if entry.caption else ""}{entry.url}')
            file = discord.File(file, Path(entry.url).name)
            await self.channel.send(entry.caption, file=file)
        else:
            raise RuntimeError(f'invalid entry {entry}')

        await asyncio.sleep(0.01)

    async def handle_meural_forward(
        self,
        entry: TinybeanEntry,
        file: Optional[io.BytesIO] = None,
    ) -> None:
        """send the entry to a meural frame"""
        if file is None:
            return

    @a.cached_property
    async def _smtp_client(self) -> SMTP:
        apikey = self.config_safe['SENDGRID_API_KEY']

        smtp_client = SMTP(hostname='smtp.sendgrid.net', port=587)
        await smtp_client.connect(username='apikey', password=apikey, start_tls=True)

        return smtp_client

    async def handle_email_forward(
        self,
        entry: TinybeanEntry,
        file: Optional[io.BytesIO] = None,
    ) -> None:
        if file is None or not entry.is_photo:
            self.info('invalid photo for email send')
            return

        if not self.config_safe.get('SENDGRID_API_KEY', ''):
            self.error('sendgrid api key missing')
            return

        if not (recipients := self.config_safe.get('EMAIL_FORWARDS', [])):
            self.error('recipients missing')
            return

        if not (from_addr := self.config_safe.get('EMAIL_FORWARDS_FROM_ADDR', '')):
            self.error('from addr missing')
            return

        from email.mime.image import MIMEImage
        from email.mime.multipart import MIMEMultipart

        message = MIMEMultipart()
        message['From'] = from_addr
        message['Subject'] = 'Hello World!'
        message.attach(MIMEImage(file.getvalue()))

        self.info(f'forwarding to {recipients}')
        client = await self._smtp_client
        await client.send_message(message, recipients=recipients)
