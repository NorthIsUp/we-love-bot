from functools import cached_property
from typing import ClassVar, Optional, Set

from nextcord import Message

from welovebot.lib.cog import Cog

ChannelIdT = int
AgeT = int


class ThreadsRequired(Cog):
    period: ClassVar[int] = 60

    class Config:
        CHANNELS: Set[int]

    @cached_property
    def channels(self) -> Set[int]:
        channels: Optional[Set[int]] = self.config_safe.get('CHANNELS', None)
        return channels or set()

    def filter_channel(self, message: Message) -> bool:
        print(message.channel.id, self.channels)
        return message.channel.id in self.channels

    @Cog.task('on_message', filter_method=filter_channel)
    async def on_message(self, message: Message):
        self.debug(f'{message.channel.id} is in channels to check')
        await message.start_thread(name=f'🧵 {message.content}')
