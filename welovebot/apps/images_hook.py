from __future__ import annotations

import json
import re
from dataclasses import dataclass
from http.client import BAD_REQUEST, OK
from typing import Callable, ClassVar, Dict, List, Optional, Union

from aiohttp.web import Request, Response

from welovebot.lib.web import WebCog


@dataclass(unsafe_hash=True)
class ImagesHook(WebCog):
    url_root: ClassVar[str] = 'email_images'

    class Config:
        IMAGE_CHANNEL: int

    @dataclass
    class Params:
        channel: int
        pattern: str
        body: str

        def __post_init__(self):
            self.channel = int(self.channel)

        @classmethod
        def from_params(cls, params: Dict[str, Union[bytes, int, str]]) -> ImagesHook.Params:
            kwargs = {}
            for name, dst in (
                ('body', str),
                ('pattern', str),
                ('channel', int),
            ):
                p = params[name]
                kwargs[name] = dst(p.decode() if isinstance(p, bytes) else p)

            return cls(**kwargs)

    @classmethod
    def parse_body(cls, body: str, pattern: str) -> List[str]:
        cls.info(f'pattern: {repr(pattern)}')
        return re.findall(pattern, body) or []

    @WebCog.route('POST', '/handle_body')
    async def handle_body(self, request: Request) -> Response:
        """accepts payload of email headers, most importantly 'Body'"""
        response: Dict[str, int] = {'status': OK}

        def _respond(status: Optional[int] = None) -> Response:
            response['status'] = status or response['status']
            return Response(text=json.dumps(response), status=response['status'])

        if not request.has_body:
            return _respond(BAD_REQUEST)

        params = ImagesHook.Params.from_params(await request.post())

        if not params.channel:
            return _respond(BAD_REQUEST)

        for url in self.parse_body(params.body, params.pattern):
            self.dispatch(
                'image_with_caption',
                source=self,
                url=url,
                discord_channel=params.channel,
                thumbnail_url=None,
            )
            response[url] = OK

        return _respond(OK)
