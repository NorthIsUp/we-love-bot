import asyncio
import imp
import logging
from dataclasses import dataclass
from functools import cached_property, wraps
from typing import Callable, ClassVar, Iterable, List, Literal, Optional
from urllib.parse import urljoin

from aiohttp import web, web_middlewares
from discord.ext import commands

from northisbot.lib.cog import Cog
from northisbot.lib.config import AppConfig

logger = logging.getLogger(__name__)
MethodsT = Literal['CONNECT', 'HEAD', 'GET', 'DELETE', 'OPTIONS', 'PATCH', 'POST', 'PUT', 'TRACE']

_NO_SLASH_ERR = "may not contain a '/'"


@dataclass
class WebCog(Cog):
    url_root: ClassVar[Optional[str]] = None

    # extra middlewares to append
    middlewares: ClassVar[List[web_middlewares._Middleware]] = []

    def __post_init__(self):
        if self.url_root is None:
            raise AttributeError(f"{self.__class__.__name__} is missing 'root' path value")

        self.url_root = self.url_root.strip('/')
        if '/' in self.url_root:
            raise ValueError(f'{self.__class__.__name__}.url_root {_NO_SLASH_ERR}')

        self.host = self.config.get('HOST', '0.0.0.0')
        self.port = self.config.get('PORT', 8080)

    @property
    def config(self) -> AppConfig:
        return AppConfig(self.bot.__class__, self.__class__)

    @cached_property
    def web_app(self) -> web.Application:
        middlewares = [web.normalize_path_middleware()] + self.middlewares
        app = web.Application(middlewares=middlewares)

        def _route_attrs() -> Iterable[Callable]:
            for name in dir(self):
                if name == 'web_app':
                    continue
                if getattr(attr := getattr(self, name), 'is_route', False):
                    yield attr

        for handler in _route_attrs():
            path = f'/{self.url_root}/{handler.path}/'
            logger.debug(f'[{self.__class__.__name__}] adding route: {handler.method} {path}')
            adder = getattr(app.router, f'add_{handler.method.lower()}')
            adder(path, handler)

        logger.debug('web app built')
        return app

    @classmethod
    def route(cls, method: MethodsT, path: str):
        path = path.strip('/')
        if '/' in path:
            raise ValueError(f"'{path}' {_NO_SLASH_ERR}")

        def decorator(func) -> Callable[[web.Request], web.Response]:
            @wraps(func)
            async def wrapper(self, request: web.Request) -> web.Response:
                return await func(self, request)

            wrapper.is_route = True
            wrapper.method = method
            wrapper.path = path

            return wrapper

        return decorator

    @Cog.on_ready_create_task
    async def start(self):
        runner = web.AppRunner(self.web_app)

        await runner.setup()
        self.site = web.TCPSite(runner, self.host, self.port)

        logger.info('starting site')
        await self.site.start()

    def cog_unload(self):
        asyncio.ensure_future(self.site.stop())
