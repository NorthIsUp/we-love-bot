import asyncio
import logging
from functools import wraps
from typing import Callable, ClassVar, Iterable, List, Literal, Optional

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

        middlewares = [web.normalize_path_middleware()] + self.middlewares
        self.app = web.Application(middlewares=middlewares)

        def _route_attrs() -> Iterable[Callable]:
            for name in dir(self):
                if getattr(attr := getattr(self, name), 'is_route', False):
                    yield attr

        for handler in _route_attrs():
            logger.info(f'adding route: {handler.method} {handler.path}')
            adder = getattr(self.app.router, f'add_{handler.method.lower()}')
            adder(handler.path, handler)

        logger.debug(self.app.router._resources)
        logger.debug(self.app.router._named_resources)
        logger.debug('server built')

    @classmethod
    def route(cls, method: MethodsT, path: str):
        path = path if path[-1] == '/' else f'{path}/'
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
        self.bot.loop.create_task(self.site.start())

    def __unload(self):
        asyncio.ensure_future(self.site.stop())
