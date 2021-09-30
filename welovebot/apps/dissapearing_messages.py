import re
from datetime import datetime, timedelta
from typing import ClassVar, Dict

from welovebot.lib.cog import Cog

ChannelIdT = int
AgeT = int

_one_hour = 3600
_default_time = _one_hour * 24


class DissapearingMessages(Cog):
    period: ClassVar[int] = 60

    @property
    def dissapearing_channels(self) -> Dict[ChannelIdT, AgeT]:
        """
        expects a list of <guild_id>:<seconds>,...
        """
        dissapearing_channels = {}
        channels_raw = self.config.get('CHANNELS') or ''
        for channel_raw in channels_raw.split(','):
            if channel_raw.count(':') == 1:
                channel, time = channel_raw.strip().split(':')
                if channel.isdigit() and (time == 'default' or time.isdigit()):
                    dissapearing_channels[int(channel)] = (
                        _default_time if time == 'default' else int(time)
                    )

        return dissapearing_channels

    @Cog.perodic_task(60)
    async def cleanup(self):
        self.info('cleaning up messages')
        for channel_id in self.dissapearing_channels:
            channel = self.bot.get_channel(channel_id)

            if not channel:
                continue

            match = re.match('^max_age=(?P<max_age>[0-9]+)', channel.topic, re.IGNORECASE)
            max_age_seconds = int(match.groups()[0]) if match else _default_time

            max_age = timedelta(seconds=max_age_seconds)
            async for message in channel.history():
                try:
                    if datetime.utcnow() - message.created_at > max_age:
                        self.info(f'cleaning {message.id}')
                        await message.delete()
                except Exception:
                    pass

            self.info('done cleaning')
