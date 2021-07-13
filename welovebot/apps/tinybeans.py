from __future__ import annotations

from datetime import datetime, timedelta
from functools import cached_property
from itertools import islice
from time import mktime, time
from typing import TYPE_CHECKING, Iterable, Sequence, Set, cast

from pytinybeans.pytinybeans import (
    PyTinybeans,
    TinybeanChild,
    TinybeanEntry,
    TinybeanJournal,
)

from welovebot.lib.cog import Cog


class Tinybeans(Cog):
    class Config:
        LOGIN: str
        PASSWORD: str
        CHILDREN_IDS: Set[int]

    @cached_property
    def last_sumthing(self) -> int:
        print((datetime.utcnow() - timedelta(days=1)).timestamp() * 1000)
        return int((datetime.utcnow() - timedelta(days=0)).timestamp() * 1000)

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

    @cached_property
    def entries(self) -> Iterable[TinybeanEntry]:
        for c in self.children:
            yield from islice(self.tinybeans.get_entries(c, last=self.last_sumthing), 200)

    @Cog.perodic_task(1)
    async def periodic_sync(self):
        for e in self.entries:
            print(e, e.type, e.blobs.o)
