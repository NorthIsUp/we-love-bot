import asyncio
import logging
from functools import wraps
from typing import Callable, ClassVar, List, Literal

from aiohttp import web, web_middlewares
from discord.ext import commands

from northisbot.lib.config import AppConfig

logger = logging.getLogger(__name__)
MethodsT = Literal["CONNECT", "HEAD", "GET", "DELETE", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"]

class WebCog(commands.Cog):

    # extra middlewares to append
    middlewares: ClassVar[List[web_middlewares._Middleware]] = []

    def __init__(self, bot):
        self.bot = bot
        config = AppConfig(bot.__class__, self.__class__)

        self.host = config.get('HOST', '0.0.0.0')
        self.port = config.get('PORT', 8080)

        self.app = web.Application(middlewares=[web.normalize_path_middleware] + self.middlewares)
        attrs = [getattr(self, h) for h in dir(self) if getattr(self, h)]
        route_attrs = [attr for attr in attrs if getattr(attr, 'is_route', None)]


        for handler in route_attrs:
            logger.info(f'adding route: {handler.method} {handler.path}')
            adder = getattr(self.app.router, f'add_{handler.method.lower()}')
            adder(handler.path, handler)

        logger.debug(self.app.router._resources)
        logger.debug(self.app.router._named_resources)
        logger.debug('server built')

    @classmethod
    def route(cls, method: MethodsT, path: str):
        def decorator(func) -> Callable[[web.Request], web.Response]:
            @wraps(func)
            async def wrapper(self, request: web.Request) -> web.Response:
                return await func(self, request)

            wrapper.is_route = True
            wrapper.method = method
            wrapper.path = path

            return wrapper
        return decorator

    @commands.Cog.listener('on_ready')
    async def start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        self.site = web.TCPSite(runner, self.host, self.port)

        logger.info('starting site')
        await self.bot.loop.create_task(self.site.start())

    def __unload(self):
        asyncio.ensure_future(self.site.stop())
