from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import cached_property
from typing import AsyncGenerator, ClassVar, Sequence, Set

import asyncstdlib as a
from pytinybeans.pytinybeans import PyTinybeans, TinybeanChild, TinybeanEntry

from welovebot.lib.cog import Cog, CogConfigCheck


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
