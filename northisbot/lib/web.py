import asyncio
import logging
from abc import ABC
from functools import wraps
from typing import Callable, Literal

from aiohttp import web
from discord.ext import commands

from northisbot.lib.config import AppConfig

logger = logging.getLogger(__name__)
MethodsT = Literal["CONNECT","HEAD","GET","DELETE","OPTIONS","PATCH""POST","PUT","TRACE",]

class WebCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        config = AppConfig(bot.__class__, self.__class__)

        self.host = config.get('HOST', '0.0.0.0')
        self.port = config.get('PORT', 8080)

        self.app = web.Application()
        attrs = [getattr(self, h) for h in dir(self) if getattr(self, h)]
        route_attrs = [attr for attr in attrs if getattr(attr, 'is_route', None)]

        for handler in route_attrs:
            logger.info(f'adding route: {handler.method} {handler.path}')
            adder = getattr(self.app.router, f'add_{handler.method.lower()}')
            adder(handler.path, handler)


    @classmethod
    def route(cls, method: MethodsT, path: str):
        def handler(f) -> Callable[[web.Request], web.Response]:
            @wraps(f)
            async def wrapper(request: web.Request) -> web.Response:
                return f(request)

            wrapper.is_route = True
            wrapper.method = method
            wrapper.path = path

            return wrapper

        return handler

    @commands.Cog.listener('on_ready')
    async def start(self):

        runner = web.AppRunner(self.app)
        await runner.setup()
        self.site = web.TCPSite(runner, self.host, self.port)

        logger.info('starting site')
        self.bot.loop.create_task(self.site.start())

    def __unload(self):
        asyncio.ensure_future(self.site.stop())
