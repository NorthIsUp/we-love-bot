from __future__ import annotations

import json
import logging
import re
import typing
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from logging.config import dictConfig
from os import environ
from pathlib import Path
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ChainMap,
    ClassVar,
    Dict,
    Optional,
    Sequence,
    Type,
    Union,
    cast,
)

from welovebot import constants

if TYPE_CHECKING:
    from .bot import Bot

logger = logging.getLogger(__name__)


class Config(ABC):
    logging: ClassVar[bool] = True

    def _log_miss_msg(self, key: str) -> None:
        if self.logging:
            logger.debug(f'config miss: {key}')

    def _log_hit_msg(self, key: str) -> None:
        if self.logging:
            logger.debug(f'config hit: {key}')

    def _log_default_msg(self, key: str) -> None:
        if self.logging:
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

    def __setitem__(self, key: str, value: str) -> None:
        key = self._key(key)
        self._setitem(key, value)

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

    def _setitem(self, key: str, value: str) -> None:
        """called by __setitem__"""
        raise RuntimeError(f'set item not supported for {self.__class__.__name__}')


@dataclass
class PrefixConfig(Config, ABC):
    default_prefix: ClassVar[str] = constants.WELOVEBOT_CONFIG_PREFIX_DEFAULT
    default_envvar: ClassVar[str] = constants.WELOVEBOT_CONFIG_PREFIX_ENVVAR

    def __init__(self, prefix: Optional[str] = None) -> None:
        self.set_prefix(prefix)

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


@dataclass
class ChainConfig(Config):
    configs: Sequence[Config]
    logging: ClassVar[bool] = False

    def _getitem(self, key: str) -> str:
        for c in self.configs:
            try:
                return c[key]
            except KeyError as e:
                if c is self.configs[-1]:
                    raise
        assert False, 'this should not be reached'


def _as_sequence(to: Type[Union[set, list, tuple]]) -> Callable[[str], Sequence[str]]:
    def _to_seq(seq: str, cls: Type = str) -> Union[set, list, tuple]:
        return to(cls(_.strip()) for _ in seq.split(','))

    return _to_seq


@dataclass
class TypedConfig(Config):
    types: Type

    def _log_hit_msg(self, key: str) -> None:
        if self.logging:
            a = self.types.__annotations__[key]
            a = a.__name__ if isinstance(a, type) else a
            logger.debug(f'config hit: {key} (as type {a})')

    def _log_default_msg(self, key: str) -> None:
        if self.logging:
            a = self.types.__annotations__[key]
            a = a.__name__ if isinstance(a, type) else a
            logger.debug(f'config default: {key} (as type {a})')

    _simple_type_map: ClassVar[Dict[str, Callable]] = {
        'str': str,
        'int': int,
        'float': float,
        'set': _as_sequence(set),
        'list': _as_sequence(list),
        'tuple': _as_sequence(tuple),
    }

    def _getdefault(self, key: str) -> str:
        return getattr(self, key, None)

    def _getitem(self, key: str) -> str:
        if (annotation := self.types.__annotations__.get(key)) is None:
            raise TypeError(f'{key} must be declared in the TypeConfig')

        item = super()._getitem(key)

        if isinstance(annotation, str) and '[' in annotation:
            match = re.match(r'^(?P<origin_name>[\w]+)\[(?P<to_cls_name>\w+)\]$', annotation)
            assert match, f"no match for '{annotation}'"
            origin_name = match.group('origin_name').lower()
            to_cls_type = self._simple_type_map[match.group('to_cls_name')]
            return self._simple_type_map[origin_name](item, to_cls_type)
        elif isinstance(annotation, typing._GenericAlias):
            origin_name = annotation.__origin__.__name__
            to_cls_name = annotation.__args__[0].__name__
            to_cls_type = self._simple_type_map[to_cls_name]
            return self._simple_type_map[origin_name](item, to_cls_type)
        elif isinstance(annotation, type):
            annotation = annotation.__name__

        return self._simple_type_map[annotation](item)


@dataclass
class TypedChainConfig(TypedConfig, ChainConfig):
    pass


class KeyT(str):
    pass


@dataclass
class EnvConfig(PrefixConfig):
    @staticmethod
    def _snake_case(s: str) -> str:
        if isinstance(s, KeyT):
            return s
        return re.sub('(?!^)([A-Z]+)', r'_\1', s).upper()

    def _getitem(self, key: str) -> str:
        return environ[key]


@dataclass
class JsonConfig(Config):
    path: Path
    logging: ClassVar[bool] = False

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            self.path = Path(self.path)

    @cached_property
    def json(self) -> Dict[str, Any]:
        if not self.path.exists():
            with self.path.open('w') as f:
                json.dump({}, f)

        with self.path.open() as f:
            j = json.load(f)
            if not isinstance(j, dict):
                raise TypeError('json config must be a dict')
            return cast(Dict[str, Any], j)

    def __enter__(self) -> JsonConfig:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self.save()

    def save(self) -> None:
        with self.path.open('w') as f:
            json.dump(self.json, f)

    def _getitem(self, key: str) -> str:
        return self.json[key]

    def _setitem(self, key: str, value: str) -> None:
        with self:
            self.json[key] = value

    def update(self, *args: Dict[str, Any], **kwargs: Any) -> None:
        with self:
            self.json.update(*args, **kwargs)

    def update_in(self, key: str, *args: Dict[str, Any], **kwargs: Any) -> None:
        with self:
            self.json[key].update(*args, **kwargs)

    def setdefault(self, key: str, default: Any = None) -> Any:
        if key not in self.json:
            with self:
                self.json[key] = default
        return self.json[key]


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
