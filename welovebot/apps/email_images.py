import asyncio
import io
import json
import re
from dataclasses import dataclass
from functools import cached_property
from http.client import BAD_REQUEST, OK
from os import stat
from pathlib import Path
from typing import Dict, List, Union
from xmlrpc.client import SERVER_ERROR

import aiohttp
import discord
from aiohttp.web import Request, Response

from welovebot.lib.web import WebCog


class EmailImages(WebCog):
    url_root = 'email_images'

    class Config:
        pass

    @dataclass
    class Params:
        channel: int
        pattern: str
        body: str

        def __post_init__(self):
            self.channel = int(self.channel)

        @classmethod
        def from_params(cls, params: Dict[str, Union[bytes, int, str]]):
            kwargs = {}
            for name, dst in (
                ('body', str),
                ('pattern', str),
                ('channel', int),
            ):
                p = params[name]
                kwargs[name] = dst(p.decode() if isinstance(p, bytes) else p)

            return cls(**kwargs)

    @WebCog.route('POST', '/handle_body')
    async def handle_body(self, request: Request) -> Response:
        """accepts payload of email headers, most importantly 'Body'"""
        response: Dict[str, int] = {'status': OK}

        if request.has_body:
            params = EmailImages.Params.from_params(await request.post())
            if (channel := self.bot.get_channel(params.channel)) is None:
                response['status'] = BAD_REQUEST
            else:
                urls = self.parse_body(params.body, params.pattern)
                for url in self.parse_body(params.body, params.pattern):
                    try:
                        self.info(f'handling url {url}')
                        await self.handle_discord_send(url, channel)
                        response[url] = OK
                    except Exception:
                        response['status'] = response[url] = SERVER_ERROR

        else:
            response['status'] = BAD_REQUEST

        return Response(text=json.dumps(response), status=response['status'])

    @classmethod
    def parse_body(cls, body: str, pattern: str) -> List[str]:
        cls.info(f'pattern: {repr(pattern)}')
        return re.findall(pattern, body) or []

    async def fetch_url_as_file(self, url: str) -> io.BytesIO:
        async with aiohttp.ClientSession() as session, session.get(url) as resp:
            return io.BytesIO(await resp.read())

    async def handle_discord_send(self, entry_url: str, channel: discord.TextChannel) -> None:
        self.info(f'posting file: {entry_url}')
        file = await self.fetch_url_as_file(entry_url)
        await channel.send(file=discord.File(file, Path(entry_url).name))
        await asyncio.sleep(0.01)
