from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from functools import cached_property
from itertools import islice
from time import mktime, time
from typing import TYPE_CHECKING, Iterable, Sequence, Set, cast

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
        db.setdefault('seen', {})
        return db

    @cached_property
    def last_sumthing(self) -> int:
        return datetime.utcnow() - timedelta(days=1)

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

    @Cog.perodic_task(hours=1)
    async def periodic_sync(self) -> None:
        for c in self.children:
            await self.handle_entries(*self.entries)

    async def handle_entries(self, *entries: TinybeanEntry) -> None:
        for entry in entries:
            if str(entry.id) not in self.db['seen']:
                message = f'{entry.caption}\n{entry.url if not entry.is_text else ""}'.strip()
                await self.channel.send(message)
                self.db['seen'] = {**self.db['seen'], **{entry.id: time()}}
                await asyncio.sleep(0.5)
