import asyncio
import re
from datetime import datetime, timedelta
from logging import getLogger
from typing import ClassVar, Dict, Final, Optional

from northisbot.lib.cog import Cog

ChannelIdT = int
AgeT = int

logger = getLogger(__name__)
_one_hour = 3600
_default_time = _one_hour * 24


class DissapearingMessages(Cog):
    dissapearing_channels: ClassVar[Dict[ChannelIdT, AgeT]] = {
        799723513014386708: _default_time,
    }

    period: ClassVar[int] = 60

    @Cog.on_ready_create_task
    async def periodic_cleanup(self):
        logger.info('starting clean loop')
        while True:
            try:
                await self.cleanup()
            except Exception as e:
                logger.exception(e)

            await asyncio.sleep(self.period)

    async def cleanup(self):
        logger.info('cleaning up messages')
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
                        logger.info(f'cleaning {message.id}')
                        await message.delete()
                except Exception:
                    pass

            logger.info('done cleaning')
