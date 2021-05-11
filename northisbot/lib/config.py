import logging
import re
from abc import ABC, abstractmethod
from asyncio.log import logger
from dataclasses import dataclass
from functools import cached_property
from os import environ
from typing import Optional, Type

logger = logging.getLogger(__name__)


class Config(ABC):
    def __getitem__(self, key: str) -> str:
        key = self._key(key)
        try:
            value = self._getitem(key)
        except KeyError:
            logger.debug(f'config miss: {key}')
            raise
        else:
            logger.debug(f'config hit: {key}')
            return value

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        try:
            key = self._key(key)
            return self[key]
        except KeyError:
            logger.debug(f'config default: {key}')
            return default

    def _key(self, key: str) -> str:
        return key

    @abstractmethod
    def _getitem(self, key: str) -> str:
        """called by __getitem__"""


@dataclass
class EnvConfig(Config):
    def __post_init__(self):
        self.prefix = self._snake_case(self.prefix)

    @cached_property
    def prefix(self) -> str:
        raise NotImplementedError('do this')

    @staticmethod
    def _snake_case(s: str) -> str:
        return re.sub('(?!^)([A-Z]+)', r'_\1', s).upper()

    @staticmethod
    def _join_prefix(*s: str) -> str:
        return ('__'.join(s)).upper()

    def _key(self, key: str) -> str:
        return key if key.startswith(f'{self.prefix}__') else self._join_prefix(self.prefix, key)

    def _getitem(self, key: str) -> str:
        return environ[key]


@dataclass
class BotConfig(EnvConfig):
    bot: Type

    def __post_init__(self) -> None:
        self.prefix = self.bot.__name__.upper()


@dataclass
class AppConfig(BotConfig):
    ext: Type

    def __post_init__(self) -> None:
        self.prefix = self._join_prefix(self.bot.__name__, self._snake_case(self.ext.__name__))


@dataclass
class GistConfig(Config):
    gist_id: int

    def __post_init__(self) -> None:
        from simplegist import Simplegist

        gh_gist = Simplegist(username='USERNAME', api_token='API_TOKEN')
        self._gist = gh_gist[self.gist_id]

    def _getitem(self, key: str) -> str:
        return self._gist[key]
