from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import cached_property
from typing import AsyncGenerator, ClassVar, Sequence, Set

import asyncstdlib as a
from pytinybeans.pytinybeans import PyTinybeans, TinybeanChild, TinybeanEntry

from welovebot.lib.cog import Cog, CogConfigCheck
from welovebot.lib.web import WebCog


@dataclass(unsafe_hash=True)
class Tinybeans(WebCog):
    tb: PyTinybeans = field(default_factory=PyTinybeans)
    check_config_safe: ClassVar[CogConfigCheck] = CogConfigCheck.RAISE

    url_root = 'tinybeans'

    class Config:
        LOGIN: str
        PASSWORD: str
        CHILDREN_IDS: Set[int]
        IMAGE_CHANNEL: int
        EMAIL_RECIPIENTS: Set[str]
        EMAIL_FROM_ADDR: str
        INTERVAL: int
        LAST_N_DAYS: int = 15

    @cached_property
    def scrape_after_date(self) -> datetime:
        last_n_days = int(self.config_safe['LAST_N_DAYS'])
        scrape_after_date = datetime.utcnow() - timedelta(days=last_n_days)
        self.info(
            f'using the last {last_n_days} days, since {scrape_after_date}',
        )
        return scrape_after_date

    @a.cached_property
    async def children(self) -> Sequence[TinybeanChild]:
        ids = set(int(c) for c in self.config_safe['CHILDREN_IDS'])
        return tuple(c for c in await self.tb.children if c.id in ids)

    async def login(self) -> bool:
        self.info(f'Logging in... (currently logged in? {self.tb.logged_in})')
        await self.tb.login(self.config_safe['LOGIN'], self.config_safe['PASSWORD'])
        return self.tb.logged_in

    async def entries(self) -> AsyncGenerator[TinybeanEntry, None]:
        entry: TinybeanEntry
        for c in await self.children:
            async for entry in self.tb.get_entries(c, limit=self.scrape_after_date):
                yield entry

    @Cog.task('on_ready')
    async def _login_on_startup(self):
        await self.login()
        self.dispatch('tinybeans_login')

    @Cog.perodic_task(listener='on_tinybeans_login', minutes='INTERVAL=15')
    async def periodic_sync(self) -> None:
        async for entry in self.entries():
            self.info(f'handling entry: {entry.id}')
            if entry.is_photo or entry.is_video:
                self.dispatch(
                    'image_with_caption',
                    source=self,
                    url=entry.url,
                    caption=entry.caption,
                    timestamp=entry.timestamp,
                    uuid=entry.uuid,
                )

    @WebCog.route('GET', '/hello')
    async def foo(self, request: Request) -> Response:
        return Response(text='hello there')
