import io
import logging
from asyncio import Lock, Semaphore
from copy import deepcopy
from dataclasses import dataclass, field
from functools import partialmethod
from optparse import Option
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, Literal, Optional, Union, cast

import aiohttp
import async_timeout
from aiohttp.client_exceptions import ClientResponseError

_LOGGER = logging.getLogger(__name__)

BASE_URL = 'https://api.meural.com/v0/'
AUTHENTICATE_PATH = 'authenticate'

JsonT = Dict[str, Any]
IdT = Union[str, int]
DataT = Union[JsonT, None]


def filter_none(*_d: JsonT, **_dd: Any) -> JsonT:
    return {k: v for d in [*_d, _dd] for k, v in d.items() if v}


@dataclass
class Meural:
    username: str = ''
    password: str = ''
    session: Optional[aiohttp.ClientSession] = aiohttp.ClientSession()
    token: Optional[str] = None
    _lock: ClassVar[Semaphore] = Semaphore(3)

    async def request(
        self,
        method: Literal['GET', 'PUT', 'POST', 'DELETE'],
        path: str,
        data: Union[JsonT, None] = None,
        form: bool = False,
        raise_for_status: bool = True,
        data_key: str = 'data',
    ) -> JsonT:
        url = f'{BASE_URL}{path}'
        kwargs: Dict[str, Any] = {}
        headers = {
            'Authorization': f'Token {self.token}',
            'x-meural-api-version': '3',
        }

        if path == AUTHENTICATE_PATH:
            headers.pop('Authorization')

        if data:
            if form:
                kwargs['data'] = aiohttp.FormData(deepcopy(data))
            elif method == 'GET':
                kwargs['query'] = data
            else:
                kwargs['json'] = data

        try:
            async with self._lock, aiohttp.ClientSession(
                headers=headers
            ) as session, session.request(
                method, url, raise_for_status=raise_for_status, **kwargs
            ) as resp:
                response: JsonT = await resp.json()
                await session.close()
            return response[data_key]

        except ClientResponseError as err:
            if err.status != 401:
                raise
            elif err.status == 401 and path == AUTHENTICATE_PATH:
                raise

            _LOGGER.info('Meural: Sending Request failed. Re-Authenticating')
            await self.login(force=True)
            return await self.request(method, path, data=data, form=form)
        except Exception as err:
            _LOGGER.error('Meural: Sending Request failed. Raising: %s' % err)
            raise

    async def get(
        self,
        path: str,
        data: DataT = None,
        form: bool = False,
        raise_for_status: bool = True,
        data_key: str = 'data',
    ) -> JsonT:
        return await self.request(
            'GET',
            path,
            data=data,
            form=form,
            raise_for_status=raise_for_status,
            data_key=data_key,
        )

    async def put(
        self,
        path: str,
        data: DataT = None,
        form: bool = False,
        raise_for_status: bool = True,
        data_key: str = 'data',
    ) -> JsonT:
        return await self.request(
            'PUT',
            path,
            data=data,
            form=form,
            raise_for_status=raise_for_status,
            data_key=data_key,
        )

    async def post(
        self,
        path: str,
        data: DataT = None,
        form: bool = False,
        raise_for_status: bool = True,
        data_key: str = 'data',
    ) -> JsonT:
        return await self.request(
            'POST',
            path,
            data=data,
            form=form,
            raise_for_status=raise_for_status,
            data_key=data_key,
        )

    async def delete(
        self,
        path: str,
        data: DataT = None,
        form: bool = False,
        raise_for_status: bool = True,
        data_key: str = 'data',
    ) -> JsonT:
        return await self.request(
            'DELETE',
            path,
            data=data,
            form=form,
            raise_for_status=raise_for_status,
            data_key=data_key,
        )

    async def login(
        self,
        username: str = '',
        password: str = '',
        force: bool = False,
        _auth_lock: Lock = Lock(),
    ) -> None:
        """Authenticate and return a token."""

        if force:
            self.token = None

        async with _auth_lock:

            if self.token:
                return

            self.username = username or self.username
            self.password = password or self.password

            assert self.username, 'username must be set before login'
            assert self.password, 'password must be set before login'

            _LOGGER.info('Meural: Authenticating')
            token = await self.post(
                AUTHENTICATE_PATH,
                data={'username': self.username, 'password': self.password},
                raise_for_status=True,
                data_key='token',
            )
            assert token and isinstance(
                token, str
            ), 'token was not provided in the authentication response'
            self.token = token

    async def get_user(self) -> JsonT:
        return await self.get('user')

    async def get_user_items(self) -> JsonT:
        return await self.get('user/items')

    async def get_user_galleries(self) -> JsonT:
        return await self.get('user/galleries')

    async def get_user_devices(self) -> JsonT:
        return await self.get('user/devices')

    async def get_user_feedback(self) -> JsonT:
        return await self.get('user/feedback')

    async def device_load_gallery(self, device_id: IdT, gallery_id: IdT):
        return await self.post(f'devices/{device_id}/galleries/{gallery_id}')

    async def device_load_item(self, device_id: IdT, item_id: IdT):
        return await self.post(f'devices/{device_id}/items/{item_id}')

    async def get_device(self, device_id: IdT) -> JsonT:
        return await self.get(f'devices/{device_id}')

    async def get_device_galleries(self, device_id: IdT) -> JsonT:
        return await self.get(f'devices/{device_id}/galleries')

    async def update_device(self, device_id: IdT, data: JsonT):
        return await self.put(f'devices/{device_id}', data)

    async def sync_device(self, device_id: IdT):
        return await self.post(f'devices/{device_id}/sync')

    async def get_item(self, item_id: IdT) -> JsonT:
        return await self.get(f'items/{item_id}')

    async def update_item(
        self,
        item_id: IdT,
        name: Optional[str] = None,
        author: Optional[str] = None,
        description: Optional[str] = None,
        medium: Optional[str] = None,
        year: Union[str, int, None] = None,
    ) -> Optional[JsonT]:
        data = filter_none(
            name=name,
            author=author,
            description=description,
            medium=medium,
            year=str(year) if year else None,
        )
        if data:
            return await self.put(f'items/{item_id}', data)
        else:
            return None

    async def add_item(
        self,
        image_bytes: io.BytesIO,
        gallery_id: Optional[IdT] = None,
        name: Optional[str] = None,
        author: Optional[str] = None,
        description: Optional[str] = None,
        medium: Optional[str] = 'photography',
        year: Optional[int] = None,
    ) -> JsonT:
        item = await self.post('items', data={'image': image_bytes}, form=True)
        item_id: int = item['id']

        await self.update_item(
            item_id,
            name=name,
            author=author,
            description=description,
            medium=medium,
            year=year,
        )
        if gallery_id:
            await self.add_to_gallery(gallery_id=gallery_id, item_id=item_id)

        return item

    async def add_to_gallery(self, gallery_id: IdT, item_id: IdT) -> JsonT:
        return await self.post(f'galleries/{gallery_id}/items/{item_id}')
