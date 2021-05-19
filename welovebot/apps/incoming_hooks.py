from aiohttp.web import Request, Response

from welovebot.lib.web import WebCog


class IncomingWebHooks(WebCog):
    url_root = 'incoming'

    @WebCog.route('GET', '/hello')
    async def foo(self, request: Request) -> Response:
        return Response(text='hello there')
