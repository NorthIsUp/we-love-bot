import asyncio
import io
import json
import re
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


class Kaymbu(WebCog):
    url_root = 'kaymbu'

    class Config:
        CHANNEL: int

    @cached_property
    def channel(self) -> discord.TextChannel:
        return self.bot.get_channel(self.config_safe['CHANNEL'])

    @WebCog.route('POST', '/new_post')
    async def new_post(self, request: Request) -> Response:
        """accepts payload of email headers, most importantly 'Body'"""

        response: Dict[str, int] = {'status': OK}

        if request.has_body:
            params = await request.post()

            for url in self.parse_body(params['Body']):
                try:
                    await self.handle_discord_send(url)
                    response[url] = OK
                except Exception:
                    response['status'] = response[url] = SERVER_ERROR

        else:
            response['status'] = BAD_REQUEST

        return Response(text=json.dumps(response), status=response['status'])

    @classmethod
    def parse_body(cls, body: Union[str, bytes]) -> List[str]:
        if isinstance(body, bytes):
            body = body.decode()

        return re.findall(r'(https://\w+\.cloudfront\.net/public/media/[\w/-]+\.jpg)', body) or []

    async def fetch_url_as_file(self, url: str) -> io.BytesIO:
        async with aiohttp.ClientSession() as session, session.get(url) as resp:
            return io.BytesIO(await resp.read())

    async def handle_discord_send(
        self,
        entry_url: str,
    ) -> None:
        self.info(f'posting file: {entry_url}')
        file = await self.fetch_url_as_file(entry_url)
        await self.channel.send(file=discord.File(file, Path(entry_url).name))
        await asyncio.sleep(0.01)
