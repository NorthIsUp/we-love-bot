from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from asyncio.log import logger
from dataclasses import dataclass
from distutils.command.config import config
from functools import cached_property
from logging.config import dictConfig
from os import environ
from typing import TYPE_CHECKING, Optional, Sequence, Type, Union

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


@dataclass
class EnvConfig(Config):
    def __post_init__(self):
        self.prefix = self._snake_case(self.prefix)

    @cached_property
    def prefix(self) -> str:
        raise NotImplementedError('prefix must be overridden')

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
    bot: Union[Type[Bot], Bot]

    def __post_init__(self) -> None:
        """try for bot.config_prefix first, otherwise the class name"""
        if prefix := getattr(self.bot, 'config_prefix', None):
            self.prefix = prefix.upper()
        elif isinstance(self.bot, type):
            self.prefix = self.bot.__name__.upper()


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


_info_config = {'handlers': ['console'], 'level': logging.INFO, 'propagate': False}


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
            '__main__': {'handlers': ['console'], 'level': logging.INFO, 'propagate': False,},
            'discord': {'handlers': ['console'], 'level': logging.INFO, 'propagate': False,},
            'northisbot': {'handlers': ['console'], 'level': logging.DEBUG, 'propagate': False,},
            'northisbot.config': {
                'handlers': ['console'],
                'level': logging.INFO,
                'propagate': False,
            },
        },
        'remove_existing_loggers': True,
    }

    dictConfig(logging_config)
