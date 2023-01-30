from __future__ import annotations

import asyncio
import io
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from http.client import OK
from pathlib import Path
from typing import AsyncGenerator, ClassVar, Dict, FrozenSet, List, Optional, Union

import aiohttp
import asyncstdlib as a
import nextcord
from aiohttp.web import Request, Response
from aiosmtplib import SMTP
from cachetools import LRUCache

from welovebot.lib.cog import Cog, CogConfigCheck
from welovebot.lib.config import JsonConfig
from welovebot.lib.frames.meural import Meural
from welovebot.lib.frames.nixplay import NixPhoto, NixPlay
from welovebot.lib.web import WebCog


@dataclass(unsafe_hash=True)
class _BaseHandler(WebCog):
    class Config:
        DB_PATH: str

    url_root: ClassVar[str] = 'images_handler'
    check_config_safe: ClassVar[CogConfigCheck] = CogConfigCheck.RAISE
    accepted_extensions: ClassVar[str] = ''

    _accepted_extensions: FrozenSet[str] = frozenset()
    _cache: LRUCache[str, io.BytesIO] = field(
        default_factory=lambda: LRUCache[str, io.BytesIO](128),
        hash=False,
    )
    _db: ClassVar[Optional[JsonConfig]] = None

    def __post_init__(self):
        _BaseHandler._db = _BaseHandler._db or JsonConfig(self.config['DB_PATH'])
        self._accepted_extensions = frozenset(self.accepted_extensions.split(','))

        print(JsonConfig.json)
        return super().__post_init__()

    @property
    def db(self) -> JsonConfig:
        assert self._db
        return self._db

    @asynccontextmanager
    async def seen(self, key: str, id: Union[int, str]) -> AsyncGenerator[Union[bool, str], None]:
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

    def is_extension_valid(self, url: str) -> bool:
        """acceptable_extensions='jpg,jpeg,png,gif,bmp,tif,tiff,heic,mpg,mp4,avi,mov,m4v,3gp,webm,mkv,3g2,zip'"""
        if (ext := Path(url).suffix.strip('.')) not in self._accepted_extensions:
            self.info(f"'{ext}' not an accepted extension")
            return False
        return True

    async def fetch_url_as_file(self, url: str) -> io.BytesIO:
        if url not in self._cache:
            async with self._lock, aiohttp.ClientSession() as session, session.get(url) as resp:
                if resp.status != 200:
                    raise RuntimeError(f'incomplete handling of {url}')
                file = io.BytesIO(await resp.read())
                file.name = Path(url).name
                self._cache[url] = file
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
        async with self.seen('discord_channel', url) as seen:
            if seen:
                return self.debug(f'already seen, skipping {url}')

            if not (channel := discord_channel or source.config_safe.get('IMAGE_CHANNEL')):
                return self.info('no channel to post image to')

            if not (file := await self.fetch_url_as_file(url)):
                return self.info('invalid image for discord send')

            self.info(f'posting file: {caption + " " if caption else ""}{url}')
            await self.bot.get_channel(channel).send(
                caption, file=nextcord.File(file, Path(url).name)
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
        async with self.seen(f'skylight', url) as seen:
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


@dataclass(unsafe_hash=True)
class ImagesNixplayHandler(_BaseHandler):

    client: NixPlay = field(default_factory=NixPlay, hash=False)

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
        async with self.seen(f'nixplay', url) as seen:
            if seen:
                return

            accpeted_extensions = 'jpg,jpeg,png,gif,bmp,tif,tiff,heic'
            if (ext := Path(url).suffix.strip('.')) not in accpeted_extensions:
                return self.info(f"'{ext}' not an accepted extension")

            self.client.login(self.config_safe['USERNAME'], self.config_safe['PASSWORD'])

            for playlist_id in self.config_safe['PLAYLIST_IDS']:
                self.client.add_photos(playlist_id, NixPhoto(photo_url=url, caption=caption))


@dataclass(unsafe_hash=True)
class ImagesMeuralHandler(_BaseHandler):

    client: Meural = field(default_factory=Meural, hash=False)
    accepted_extensions: ClassVar[str] = 'jpg,jpeg,png,gif,bmp,tif,tiff,heic'

    class Config:
        USERNAME: str
        PASSWORD: str
        PLAYLIST_IDS: List[int]

    @Cog.task('on_image_with_caption')
    async def handle_meural(
        self,
        source: Cog,
        url: str,
        uuid: Optional[str] = None,
        caption: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        **kwargs: str,
    ):
        async with self.seen(f'meural', url) as seen:
            if seen:
                return

            if not self.is_extension_valid(url):
                return

            await self.client.login(self.config_safe['USERNAME'], self.config_safe['PASSWORD'])
            image_file = await self.fetch_url_as_file(url)

            for playlist_id in self.config_safe['PLAYLIST_IDS']:
                await self.client.add_item(
                    image_file,
                    playlist_id,
                    name=uuid,
                    description=caption,
                    year=timestamp.year if timestamp else None,
                )


@dataclass(unsafe_hash=True)
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

        async with self.seen('email_forward', url) as seen:
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
