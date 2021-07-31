from __future__ import annotations

import asyncio
import io
from datetime import datetime, timedelta
from functools import cached_property
from itertools import islice
from pathlib import Path
from time import mktime, time
from typing import TYPE_CHECKING, Dict, Iterable, Sequence, Set, Union, cast

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


class Tinybeans(Cog):
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

    @cached_property
    def tinybeans(self) -> PyTinybeans:
        from pytinybeans import PyTinybeans

        tb = PyTinybeans()
        tb.login(self.config_safe['LOGIN'], self.config_safe['PASSWORD'])

        return tb

    @cached_property
    def children(self) -> Sequence[TinybeanChild]:
        ids = set(int(c) for c in self.config_safe['CHILDREN_IDS'])
        return tuple(
            c for c in cast(Iterable[TinybeanChild], self.tinybeans.children) if c.id in ids
        )

    @property
    def entries(self) -> Iterable[TinybeanEntry]:
        for c in self.children:
            yield from self.tinybeans.get_entries(c, limit=self.last_sumthing)

    @Cog.perodic_task(minutes=15)
    async def periodic_sync(self) -> None:
        await self.handle_entries(*self.entries)

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

    async def handle_entries(self, *entries: TinybeanEntry) -> None:
        for entry in entries:
            if not self.seen(entry.id):
                if entry.is_text:
                    await self.channel.send(entry.caption)
                else:
                    file = await self.fetch_url_as_file(entry.url)
                    await self.channel.send(entry.caption, file=file)

                await asyncio.sleep(0.5)
