from __future__ import annotations

import asyncio
import logging
from abc import ABC
from asyncio import Semaphore
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, ClassVar, Iterable, List, Literal, Optional

from aiohttp import web, web_middlewares

from .cog import Cog

logger = logging.getLogger(__name__)
MethodsT = Literal['CONNECT', 'HEAD', 'GET', 'DELETE', 'OPTIONS', 'PATCH', 'POST', 'PUT', 'TRACE']

_NO_SLASH_ERR = "may not contain a '/'"


HandlerT = Callable[[web.Request], web.Response]


@dataclass
class WebCog(Cog):
    class Config:
        HOST: str = '0.0.0.0'
        PORT: int = 8080

    url_root: ClassVar[Optional[str]] = None

    # extra middlewares to append
    middlewares: ClassVar[List[web_middlewares._Middleware]] = []
    concurrency: ClassVar[int] = 10

    _web_app: ClassVar[web.Application] = web.Application()
    _site: ClassVar[Optional[web.TCPSite]] = None
    _lock: Semaphore = Semaphore()

    def __post_init__(self):
        if self.url_root is None:
            raise AttributeError(f"{self.__class__.__name__} is missing 'root' path value")

        self.url_root = self.url_root.strip('/')
        if '/' in self.url_root:
            raise ValueError(f'{self.__class__.__name__}.url_root {_NO_SLASH_ERR}')

        if self.concurrency > 1:
            self._lock = Semaphore(self.concurrency)

        self.add_subapp()

    def add_subapp(self) -> web.Application:
        middlewares = [web.normalize_path_middleware()] + self.middlewares
        app = web.Application(middlewares=middlewares)

        def _route_attrs() -> Iterable[HandlerT]:
            # check attrs but skip the base ones to avoid property side effects
            for name in {*dir(self)} - {'web_app', *dir(Cog)}:
                if getattr(attr := getattr(self, name), 'is_route', False):
                    yield attr

        for handler in _route_attrs():
            path = f'/{handler.path}/'
            logger.debug(
                f'[{self.__class__.__name__}] adding route: {handler.method} /{self.url_root}{path}'
            )
            adder = getattr(app.router, f'add_{handler.method.lower()}')
            adder(path, handler)

        logger.debug('web app built')

        self._web_app.add_subapp(f'/{self.url_root}', app)
        return self._web_app

    @classmethod
    def route(cls, method: MethodsT, path: str):
        path = path.strip('/')
        if '/' in path:
            raise ValueError(f"'{path}' {_NO_SLASH_ERR}")

        def decorator(func: HandlerT) -> HandlerT:
            @wraps(func)
            async def wrapper(self, request: web.Request) -> web.Response:
                return await func(self, request)

            wrapper.is_route = True
            wrapper.method = method
            wrapper.path = path

            return wrapper

        return decorator

    @Cog.on_ready
    async def start(self):
        async with WebCog._lock:
            if WebCog._site:
                return logger.info('site alredy started')

            logger.info('starting site')

            host: str = self.config['HOST']
            port: int = self.config['PORT']

            runner = web.AppRunner(self._web_app)
            await runner.setup()

            WebCog._site = web.TCPSite(runner, host, port)
            await WebCog._site.start()

            logger.info(f'started site on {host}:{port}')

    def cog_unload(self):
        asyncio.ensure_future(WebCog._site.stop())
