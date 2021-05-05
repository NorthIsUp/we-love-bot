from aiohttp.web import Request, Response

from northisbot.lib.web import WebCog


class IncomingWebHooks(WebCog):

    @WebCog.route('GET', '/hello')
    async def foo(request: Request) -> Response:
        return Response('hello there')
