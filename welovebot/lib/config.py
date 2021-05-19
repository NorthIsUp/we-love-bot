from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from logging.config import dictConfig
from os import environ
from typing import TYPE_CHECKING, ChainMap, ClassVar, Optional, Sequence, Type, Union

if TYPE_CHECKING:
    from .bot import Bot

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
class ChainConfig(Config):
    configs: Sequence[Config]

    def _getitem(self, key: str) -> str:
        for c in self.configs:
            try:
                return c[key]
            except KeyError as e:
                if c is self.configs[-1]:
                    raise
        assert False, 'this should not be reached'


class KeyT(str):
    pass


@dataclass
class EnvConfig(Config):

    default_prefix: ClassVar[str] = 'EZBOT'
    default_envvar: ClassVar[str] = 'EZBOT_CONFIG_PREFIX'

    def __init__(self, prefix: Optional[str] = None) -> None:
        self.set_prefix(prefix)

    @staticmethod
    def _snake_case(s: str) -> str:
        if isinstance(s, KeyT):
            return s
        return re.sub('(?!^)([A-Z]+)', r'_\1', s).upper()

    @staticmethod
    def _join_prefix(*s: str) -> KeyT:
        return KeyT(('__'.join(s)).upper())

    @cached_property
    def prefix(self):
        raise NotImplementedError('provide a prefix')

    def set_prefix(self, prefix: Optional[str]) -> None:
        self.prefix = prefix or environ.get(self.default_envvar, self.default_prefix)

    def _key(self, key: str) -> KeyT:
        if isinstance(key, KeyT):
            return key
        return self._join_prefix(self.prefix, key)

    def _getitem(self, key: str) -> str:
        return environ[key]


@dataclass
class BotConfig(EnvConfig):
    bot: Union[Type[Bot], Bot]

    def __post_init__(self) -> None:
        """try for bot.config_prefix first, otherwise the default prefix"""
        self.set_prefix(getattr(self.bot, 'config_prefix', None))


@dataclass
class CogConfig(BotConfig):
    ext: Type

    def __post_init__(self) -> None:
        super().__post_init__()
        self.prefix = self._join_prefix(self.prefix, self._snake_case(self.ext.__name__))


@dataclass
class GistConfig(Config):
    gist_id: int

    def __post_init__(self) -> None:
        from simplegist import Simplegist

        gh_gist = Simplegist(username='USERNAME', api_token='API_TOKEN')
        self._gist = gh_gist[self.gist_id]

    def _getitem(self, key: str) -> str:
        return self._gist[key]


_base_config = {'handlers': ['console'], 'level': logging.ERROR, 'propagate': False}
_info_config = ChainMap({'level': logging.INFO}, _base_config)
_debug_config = ChainMap({'level': logging.DEBUG}, _base_config)


def configure_logging():
    logging_config = {
        'version': 1,
        'formatters': {'f': {'format': '%(asctime)s %(levelname)-8s %(name)-20s -- %(message)s'}},
        'handlers': {
            'console': {'class': 'logging.StreamHandler', 'formatter': 'f', 'level': logging.DEBUG,}
        },
        'loggers': {
            '': {'handlers': ['console'], 'level': logging.DEBUG, 'propagate': True},
            'aiohttp.access': _info_config,
            'aiohttp.client': _info_config,
            'aiohttp.internal': _info_config,
            'aiohttp.server': _info_config,
            'aiohttp.web': _info_config,
            'aiohttp.websocket': _info_config,
            '__main__': _info_config,
            'discord': _info_config,
            'welovebot': _debug_config,
        },
        'remove_existing_loggers': True,
    }

    dictConfig(logging_config)
