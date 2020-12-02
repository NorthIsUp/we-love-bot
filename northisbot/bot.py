from logging import getLogger
from pathlib import Path

import discord
from discord.ext import commands

logger = getLogger(__name__)


class NorthIsBot(commands.Bot):
    async def on_ready(self) -> None:
        logger.debug("Logged on as {0}!".format(self.user))

    def discover_extensions(self, path: Path):
        """load all cogs under path"""

    async def send_message(
        self, message: discord.Message, response: str, img_url: str = None
    ):
        for small_response in (r.strip() for r in response.split("\n\n") if r.strip()):
            await message.channel.trigger_typing()
            await message.channel.send(small_response)
        if img_url:
            await message.channel.trigger_typing()
            await message.channel.send(img_url)
