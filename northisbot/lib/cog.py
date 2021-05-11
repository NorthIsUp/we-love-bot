from __future__ import annotations

from dataclasses import dataclass
from functools import wraps

from discord.ext import commands


@dataclass
class Cog(commands.Cog):
    bot: commands.Bot

    @classmethod
    def on_ready(cls, func):
        return cls.listener('on_ready')(func)

    @classmethod
    def on_ready_create_task(cls, func):
        @cls.listener('on_ready')
        @wraps(func)
        async def wrapper(self):
            self.bot.loop.create_task(func(self))

        return wrapper
