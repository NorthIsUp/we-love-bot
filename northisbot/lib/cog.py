from dataclasses import dataclass
from functools import wraps

from discord.ext import commands

from northisbot.bot import NorthIsBot


@dataclass
class Cog(commands.Cog):
    bot: NorthIsBot

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
