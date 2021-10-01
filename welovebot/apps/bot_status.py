from asyncio import sleep
from functools import cached_property

from welovebot.prelude import ChannelT, Cog


class BotStatus(Cog):
    class Config:
        CHANNEL: int

    @cached_property
    def channel(self) -> ChannelT:
        channel = self.bot.get_channel(self.config_safe['CHANNEL'])
        assert channel is not None
        return channel

    @Cog.on_ready
    async def starting_up(self):
        if self.channel is not None:
            await self.channel.send(f'🚀 `{self.bot.config_prefix}` starting up')

    @Cog.on_ready
    async def shutting_down(self):
        if self.channel is not None:
            try:
                while True:
                    await sleep(30000)
            finally:
                await self.channel.send(f'🛑 `{self.bot.config_prefix}` shutting down')
