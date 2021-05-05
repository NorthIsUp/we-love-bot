import logging
import re
from abc import ABC, abstractmethod
from asyncio.log import logger
from dataclasses import dataclass
from os import environ
from typing import Type

logger = logging.getLogger(__name__)

_MISSING = object()

class Config(ABC):
    def get(self, key: str, default: str=_MISSING) -> str:
        try:
            key = self._key(key)
            value = self[key]
        except KeyError:
            if default is not _MISSING:
                logger.debug(f'config default: {key}')
                return default
            logger.debug(f'config miss: {key}')
            raise
        else:
            logger.debug(f'config hit: {key}')

    def _key(self, key: str)-> str:
        return key


    @abstractmethod
    def __getitem__(self, key: str) -> str:
        pass

@dataclass
class AppConfig(Config):
    bot: Type
    ext: Type

    def __post_init__(self) -> None:
        env_prefix = re.sub('(?!^)([A-Z]+)', r'_\1', self.ext.__name__).upper()
        self.prefix = f'{self.bot.__name__.upper()}__{env_prefix}'

    def _key(self, key: str) -> str:
        return f'{self.prefix}__{key.upper()}'

    def __getitem__(self, key: str) -> str:
        return environ[key]

@dataclass
class GistConfig(Config):
    gist_id: int

    def __post_init__(self) -> None:
        from simplegist import Simplegist
        gh_gist = Simplegist(username="USERNAME", api_token="API_TOKEN")
        self._gist = gh_gist[self.gist_id]


    def __getitem__(self, key: str) -> str:
        return self._gist[key]
