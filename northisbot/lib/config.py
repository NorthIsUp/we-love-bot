import logging
import re
from abc import ABC, abstractmethod
from asyncio.log import logger
from dataclasses import dataclass
from functools import cached_property
from os import environ
from typing import Type

logger = logging.getLogger(__name__)

_MISSING = object()


class Config(ABC):
    def get(self, key: str, default: str = _MISSING) -> str:
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

    def _key(self, key: str) -> str:
        return key

    @abstractmethod
    def __getitem__(self, key: str) -> str:
        pass


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
        return self._join_prefix(self.prefix, key)

    def __getitem__(self, key: str) -> str:
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

    def __getitem__(self, key: str) -> str:
        return self._gist[key]
