from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Dict, Literal, Optional
from urllib.parse import urlparse, urlsplit

import async_timeout
import requests
from aiohttp import ClientSession, MultipartWriter

from welovebot.lib.cog import Cog

from .meural_api import MeuralApi


@dataclass
class Meural(Cog):
    class Config:
        USERNAME: str
        PASSWORD: str
        GALLERY_ID: int
        TINYBEANS_SYNC: bool

    meural: MeuralApi = MeuralApi()

    def __post_init__(self):
        self.meural.logger = self.logger

    @Cog.task
    async def setup(self):
        print('pre-auth')
        username = self.config_safe['USERNAME']
        password = self.config_safe['PASSWORD']
        gallery_id = self.config_safe['GALLERY_ID']

        await self.meural.authenticate(username, password)

        item_id = await self.meural.upload_item_from_url(
            'https://tinybeans.com/pv/e/407545284/150bb51e-e0cd-4333-a0b9-3c78a0dd1066-o.jpg'
        )

        await self.meural.add_item_to_gallery(gallery_id=gallery_id, item_id=item_id)

    @Cog.task
    async def scrape_tinybeans(self):
        if not self.config_safe.get('TINYBEANS_SYNC', False):
            from pytinybeans import PyTinybeans

            tb = PyTinybeans()
            tb.login(
                self.bot.config['TINYBEANS__LOGIN'],
                self.bot.config['TINYBEANS__PASSWORD'],
            )
