from __future__ import annotations

import asyncio
import io
import json
from asyncio import Semaphore
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from http.client import OK
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Union

import aiohttp
import asyncstdlib as a
import discord
from aiohttp.web import Request, Response
from aiosmtplib import SMTP
from cachetools import LRUCache

from welovebot.lib.cog import Cog, CogConfigCheck
from welovebot.lib.config import JsonConfig
from welovebot.lib.frames.nixplay import NixPhoto, NixPlay
from welovebot.lib.web import WebCog


@dataclass
class _BaseHandler(WebCog):
    class Config:
        DB_PATH: str

    url_root: ClassVar[str] = 'images_handler'
    check_config_safe: ClassVar[CogConfigCheck] = CogConfigCheck.RAISE
    _lock: Semaphore = field(default_factory=Semaphore)
    _cache: LRUCache[str, io.BytesIO] = field(
        default_factory=lambda: LRUCache[str, io.BytesIO](128)
    )
    _db: ClassVar[Optional[JsonConfig]] = None

    def __post_init__(self):
        _BaseHandler._db = _BaseHandler._db or JsonConfig(self.config['DB_PATH'])
        print(JsonConfig.json)
        return super().__post_init__()

    @property
    def db(self) -> JsonConfig:
        assert self._db
        return self._db

    @contextmanager
    def seen(self, key: str, id: Union[int, str]) -> float:
        with self.db:
            seen_db = self.db.setdefault('seen', {}).setdefault(key, {})
            seen: Union[bool, str] = seen_db.get(id, False)

            if isinstance(seen, str):
                seen = seen.lower()
                if seen.startswith('error'):
                    seen = False
            if not seen:
                seen_db[id] = datetime.utcnow().isoformat()

            try:
                yield seen
            except (TimeoutError, asyncio.TimeoutError) as e:
                next_try = (datetime.utcnow() + timedelta(hours=1)).isoformat()
                seen_db[id] = f'error: TimeoutError {next_try}'
            except Exception as e:
                seen_db[id] = f'error: {e.__class__.__name__}'
                self.exception(e)
                raise
            except SystemExit as e:
                seen_db[id] = f'error: SystemExit'
                self.error(f'unclean exit for {id}: {e.__class__.__name__}')
            except BaseException as e:
                seen_db[id] = f'error: {e.__class__.__name__}'
                self.exception(e)

    async def fetch_url_as_file(self, url: str) -> io.BytesIO:
        if url not in self._cache:
            async with self._lock, aiohttp.ClientSession() as session, session.get(url) as resp:
                if resp.status != 200:
                    raise RuntimeError(f'incomplete handling of {url}')
                self._cache[url] = io.BytesIO(await resp.read())
            self.debug(f'fetched file for url {url}')
        else:
            self.debug(f'cached file for url {url}')

        return self._cache[url]

    @WebCog.route('GET', '/db')
    async def show_db(self, request: Request) -> Response:
        return Response(text=json.dumps(self.db.json, indent=2), status=OK)


class ImagesDiscordHandler(_BaseHandler):
    @Cog.task('on_image_with_caption')
    async def handle_discord_forward(
        self,
        source: Cog,
        url: str,
        caption: Optional[str] = None,
        discord_channel: Optional[int] = None,
        **kwargs,
    ) -> None:
        with self.seen('discord_channel', url) as seen:
            if seen:
                return self.debug(f'already seen, skipping {url}')

            if not (channel := discord_channel or source.config_safe.get('IMAGE_CHANNEL')):
                return self.info('no channel to post image to')

            if not (file := await self.fetch_url_as_file(url)):
                return self.info('invalid image for discord send')

            self.info(f'posting file: {caption + " " if caption else ""}{url}')
            await self.bot.get_channel(channel).send(
                caption, file=discord.File(file, Path(url).name)
            )


class ImagesSkylightHandler(_BaseHandler):
    class Config:
        AUTH: str
        FRAME_IDS: List[str]

    @Cog.task('on_image_with_caption')
    async def handle_skylight(
        self,
        source: Cog,
        url: str,
        caption: Optional[str] = None,
        **kwargs,
    ):
        with self.seen(f'skylight', url) as seen:
            if seen:
                return

            accpeted_extensions = (
                'jpg,jpeg,png,gif,bmp,tif,tiff,heic,mpg,mp4,avi,mov,m4v,3gp,webm,mkv,3g2,zip'
            )
            if (ext := Path(url).suffix.strip('.')) not in accpeted_extensions:
                return self.info(f"'{ext}' not an accepted extension")

            if not (file := await self.fetch_url_as_file(url)):
                return self.info('invalid image for email send')

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://app.ourskylight.com/api/upload_urls',
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Basic {self.config_safe["AUTH"]}',
                    },
                    data=json.dumps(
                        {
                            'ext': ext,
                            'frame_ids': self.config_safe['FRAME_IDS'],
                            'caption': caption,
                        }
                    ),
                ) as resp:
                    data: Dict[str, str] = (await resp.json()).get('data', [{}])[0]
                    url = data['url']

                async with session.put(
                    url,
                    data=file,
                    headers={'Content-Type': f'image/{ext}'},
                ) as resp:
                    self.debug(f'{resp.status}: uploaded {url}')


@dataclass
class ImagesNixplayHandler(_BaseHandler):

    client = NixPlay()

    class Config:
        USERNAME: str
        PASSWORD: str
        PLAYLIST_IDS: List[int]

    @Cog.task('on_image_with_caption')
    async def handle_nixplay(
        self,
        source: Cog,
        url: str,
        caption: Optional[str] = None,
        **kwargs: str,
    ):
        with self.seen(f'nixplay', url) as seen:
            if seen:
                return

            accpeted_extensions = (
                'jpg,jpeg,png,gif,bmp,tif,tiff,heic,mpg,mp4,avi,mov,m4v,3gp,webm,mkv,3g2,zip'
            )
            if (ext := Path(url).suffix.strip('.')) not in accpeted_extensions:
                return self.info(f"'{ext}' not an accepted extension")

            self.client.login(self.config_safe['USERNAME'], self.config_safe['PASSWORD'])

            for playlist_id in self.config_safe['PLAYLIST_IDS']:
                self.client.add_photos(playlist_id, NixPhoto(photo_url=url, caption=caption))


@dataclass
class ImagesEmailHandler(_BaseHandler):
    class Config:
        ENABLED: bool = False
        SENDGRID_API_KEY: str

    @a.cached_property
    async def _smtp_client(self, _client: SMTP = SMTP()) -> SMTP:
        if not _client.is_connected:
            async with self._lock:
                await _client.connect(
                    hostname='smtp.sendgrid.net',
                    port=587,
                    username='apikey',
                    password=self.config_safe['SENDGRID_API_KEY'],
                    start_tls=True,
                )
        return _client

    @Cog.task('on_image_with_caption')
    async def handle_email_forward(
        self,
        source: Cog,
        url: str,
        caption: Optional[str] = None,
        **kwargs,
    ) -> None:

        if not (email_recipients := source.config_safe['EMAIL_RECIPIENTS']):
            return self.error('recipients missing')

        if not (email_from_addr := source.config_safe['EMAIL_FROM_ADDR']):
            return self.error('from addr missing')

        with self.seen('email_forward', url) as seen:
            if seen:
                return self.debug(f'already seen, skipping {url}')

            if not (file := await self.fetch_url_as_file(url)):
                return self.info('invalid image for email send')

            try:
                from email.mime.image import MIMEImage
                from email.mime.multipart import MIMEMultipart

                message = MIMEMultipart()
                message['From'] = email_from_addr
                message['Subject'] = caption or 'Hello World!'
                message.attach(MIMEImage(file.getvalue()))
            except TypeError as e:
                return self.exception(e)

            self.info(f'forwarding to {email_recipients}')
            _client: SMTP = await self._smtp_client
            results, msg = await _client.send_message(message, recipients=email_recipients)
            for recipient, response in results.items():
                self.debug(f'[{msg}] {recipient} got email {response}')
            self.info(f'finished sendign to {email_recipients}')
