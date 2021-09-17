from http.client import BAD_REQUEST, OK

from aiohttp.web import Request, Response

from welovebot.lib.web import WebCog


class Kaymbu(WebCog):
    url_root = 'kaymbu'

    class Config:
        pass

    @WebCog.route('POST', '/new_post')
    async def foo(self, request: Request) -> Response:
        print(request.__dict__)
        status = OK
        if request.has_body:
            body = await request.read()
            print(body)
        else:
            status = BAD_REQUEST

        status = BAD_REQUEST
        return Response(text='hello there', status=status)
