from aiohttp.web import Request, Response

from welovebot.lib.config import Config
from welovebot.lib.web import WebCog


class Kaymbu(WebCog):
    url_root = 'kaymbu'

    class Config(Config):
        pass

    @WebCog.route('GET', '/new_post')
    async def foo(self, request: Request) -> Response:
        print(request.__dict__)
        return Response(text='hello there')
