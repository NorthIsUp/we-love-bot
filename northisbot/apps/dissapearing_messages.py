import asyncio
import re
from datetime import datetime, timedelta
from logging import getLogger
from typing import ClassVar, Dict

from discord.ext import commands

ChannelIdT = int
AgeT = int

logger = getLogger(__name__)
_one_hour = 3600


class DissapearingMessages(commands.Cog):
    dissapearing_channels: ClassVar[Dict[ChannelIdT, AgeT]] = {
        799723513014386708: 6 * _one_hour,
    }

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info('starting clean loop')
        self.bot.loop.create_task(self.periodic_cleanup())

    async def periodic_cleanup(self):
        while True:
            try:
                await self.cleanup()
            except Exception as e:
                logger.exception(e)
            await asyncio.sleep(60)

    async def cleanup(self):
        logger.info('cleaning up messages')
        for channel_id, age_in_seconds in self.dissapearing_channels.items():
            channel = self.bot.get_channel(channel_id)

            if not channel:
                continue

            match = re.match(
                '^max_age=(?P<max_age>[0-9]+)', channel.topic, re.IGNORECASE
            )
            if match:
                max_age = match.groups()[0]
            else:
                max_age = timedelta(seconds=age_in_seconds)

            async for message in channel.history():
                try:
                    if datetime.utcnow() - message.created_at > max_age:
                        logger.info(f'cleaning {message.id}')
                        await message.delete()
                except Exception:
                    pass

            logger.info('done cleaning')
