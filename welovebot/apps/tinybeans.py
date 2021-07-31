from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import cached_property
from itertools import islice
from pathlib import Path
from time import mktime, time
from types import coroutine
from typing import (
    TYPE_CHECKING,
    AsyncGenerator,
    Dict,
    Iterable,
    Sequence,
    Set,
    Union,
    cast,
)

import aiohttp
import discord
from pytinybeans.pytinybeans import (
    PyTinybeans,
    TinybeanChild,
    TinybeanEntry,
    TinybeanJournal,
)

from welovebot.lib.cog import Cog
from welovebot.lib.config import JsonConfig


@dataclass
class Tinybeans(Cog):
    tb: PyTinybeans = field(default_factory=PyTinybeans)

    class Config:
        LOGIN: str
        PASSWORD: str
        CHILDREN_IDS: Set[int]
        CHANNEL: int
        DB_PATH: str

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

    @cached_property
    async def children(self) -> Sequence[TinybeanChild]:
        ids = set(int(c) for c in self.config_safe['CHILDREN_IDS'])
        return tuple(c for c in await self.tb.children if c.id in ids)

    async def entries(self) -> AsyncGenerator[TinybeanEntry, None]:
        for c in await self.children:
            async for entry in self.tb.get_entries(c, limit=self.last_sumthing):
                yield entry

    @Cog.perodic_task(minutes=15)
    async def periodic_sync(self) -> None:
        logged_in = await self.login()
        self.debug(f'login success? {logged_in}')
        await self.handle_entries(self.entries())

    def seen(self, id: Union[str, int], update: bool = True) -> bool:
        id = str(id)
        seen = self.db['seen'].get(id, False)

        if not seen:
            self.db.update_in('seen', {id: time()})

        return seen

    async def fetch_url_as_file(self, url):
        async with aiohttp.ClientSession() as session, session.get(url) as resp:
            if resp.status != 200:
                return await channel.send('Could not download file...')
            data = io.BytesIO(await resp.read())
            return discord.File(data, Path(url).name)

    async def handle_entries(self, entries: AsyncGenerator[TinybeanEntry, None]) -> None:
        async for entry in entries:
            if not self.seen(entry.id):
                if entry.is_text:
                    self.info(f'posting text: {entry.caption}')
                    await self.channel.send(entry.caption)
                else:
                    self.info(
                        f'posting file: {entry.caption + " " if entry.caption else ""}{entry.url}'
                    )
                    file = await self.fetch_url_as_file(entry.url)
                    await self.channel.send(entry.caption, file=file)

                await asyncio.sleep(0.5)
