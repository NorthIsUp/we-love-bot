from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from logging.config import dictConfig
from os import environ
from typing import (
    TYPE_CHECKING,
    Callable,
    ChainMap,
    ClassVar,
    Dict,
    Iterable,
    Mapping,
    Optional,
    Sequence,
    Type,
    Union,
)

if TYPE_CHECKING:
    from .bot import Bot

logger = logging.getLogger(__name__)


class Config(ABC):
    def _log_miss_msg(self, key: str) -> None:
        logger.debug(f'config miss: {key}')

    def _log_hit_msg(self, key: str) -> None:
        logger.debug(f'config hit: {key}')

    def _log_default_msg(self, key: str) -> None:
        logger.debug(f'config default: {key}')

    def __getitem__(self, key: str) -> str:
        key = self._key(key)
        try:
            value = self._getitem(key)
        except KeyError:
            self._log_miss_msg(key)
            raise
        else:
            self._log_hit_msg(key)
            return value

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        try:
            key = self._key(key)
            return self[key]
        except KeyError:
            self._log_default_msg(key)
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
class TypedChainConfig(ChainConfig):
    types: Type

    def _log_hit_msg(self, key: str) -> None:
        a = self.types.__annotations__[key]
        a = a.__name__ if isinstance(a, type) else a
        logger.debug(f'config hit: {key} (as type {a})')

    def _log_default_msg(self, key: str) -> None:
        a = self.types.__annotations__[key]
        a = a.__name__ if isinstance(a, type) else a
        logger.debug(f'config default: {key} (as type {a})')

    def _as_sequence(
        to: Union[Type[set], Type[list], Type[tuple]]
    ) -> Callable[[str], Sequence[str]]:
        def _to_seq(seq: str, cls: Type = str) -> Union[set, list, tuple]:
            return to(cls(_.strip()) for _ in seq.split(','))

        return _to_seq

    _simple_type_map: ClassVar[Dict[str, Callable]] = {
        'str': str,
        'int': int,
        'float': float,
        'Set': _as_sequence(set),
        'List': _as_sequence(list),
        'Tuple': _as_sequence(tuple),
    }

    def _getitem(self, key: str) -> str:
        if (annotation := self.types.__annotations__.get(key)) is None:
            raise TypeError(f'{key} must be declared in the TypeConfig')

        item = super()._getitem(key)
        annotation = annotation.__name__ if isinstance(annotation, type) else annotation

        # logger.debug(f"config hit: {key} (as type {annotation})")
        if '[' in annotation:
            sequence, to_cls_name = annotation[:-1].split('[')
            to_cls = self._simple_type_map[to_cls_name]
            return self._simple_type_map[sequence](item, to_cls)
        else:
            return self._simple_type_map[annotation](item)


class KeyT(str):
    pass


@dataclass
class EnvConfig(Config):

    default_prefix: ClassVar[str] = 'WELOVEBOT'
    default_envvar: ClassVar[str] = 'WELOVEBOT_CONFIG_PREFIX'

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
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'f',
                'level': logging.DEBUG,
            }
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
