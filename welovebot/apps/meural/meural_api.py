import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Mapping, Optional
from urllib.parse import urlsplit

import async_timeout
from aiohttp import ClientSession, MultipartWriter

logger = logging.getLogger(__name__)

_EXTENSIONS = {
    'bmp',
    'dib',
    'gif',
    'tif',
    'tiff',
    'jfif',
    'jpe',
    'jpg',
    'jpeg',
    'pbm',
    'pgm',
    'ppm',
    'pnm',
    'png',
    'apng',
    'blp',
    'bufr',
    'cur',
    'pcx',
    'dcx',
    'dds',
    'ps',
    'eps',
    'fit',
    'fits',
    'fli',
    'flc',
    'fpx',
    'ftc',
    'ftu',
    'gbr',
    'grib',
    'h5',
    'hdf',
    'jp2',
    'j2k',
    'jpc',
    'jpf',
    'jpx',
    'j2c',
    'icns',
    'ico',
    'im',
    'iim',
    'mic',
    'mpg',
    'mpeg',
    'mpo',
    'msp',
    'palm',
    'pcd',
    'pdf',
    'pxr',
    'psd',
    'bw',
    'rgb',
    'rgba',
    'sgi',
    'ras',
    'tga',
    'icb',
    'vda',
    'vst',
    'webp',
    'wmf',
    'emf',
    'xbm',
    'xpm',
    'dng',
    'nef',
    'cr2',
}


@dataclass
class MeuralApi:
    netloc: str = 'api.meural.com'
    version: int = 1
    token: str = ''
    session: ClientSession = ClientSession()
    auto_auth: bool = True

    def __post_init__(self):
        self.url = f'https://{self.netloc}/v{self.version}'

    async def request(
        self,
        method: Literal['GET', 'POST', 'PUT', 'DELETE'],
        path: str,
        raise_for_status: bool = True,
        just_data: bool = True,
        timeout: int = 10,
        api_version: int = 3,
        **request_kwargs: Any,
    ) -> Dict[str, Any]:
        url = f'{self.url}/{path}'
        request_kwargs.setdefault('headers', {}).update(
            {
                'Authorization': f'Token {self.token}',
                'x-meural-api-version': str(api_version),
            }
        )

        if path == 'authenticate':
            request_kwargs['headers'] = {}

        with async_timeout.timeout(timeout):
            response = await self.session.request(method, url, **request_kwargs)

        if response.status >= 400:
            logger.error(await response.text())

        if raise_for_status:
            response.raise_for_status()

        response_json = await response.json()
        return response_json['data'] if just_data else response_json

    async def get(self, path: str, **kwargs: Any) -> Dict[str, Any]:
        for k in ('image', 'data'):
            if k in kwargs:
                raise ValueError(f'{k} is not supported for GET requests')

        if 'image' in kwargs:
            raise ValueError('image is not supported for GET requests')

        return await self.request('GET', path, **kwargs)

    async def post(
        self,
        path: str,
        files: Optional[Mapping[str, bytes]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if files:
            kwargs['data'] = mpwriter = MultipartWriter('form-data')
            for image_name, image_data in files.items():
                part = mpwriter.append(image_data)
                part.set_content_disposition('attachment', name='image', filename=image_name)

        return await self.request('POST', path, **kwargs)

    async def put(self, path: str, **kwargs) -> Dict[str, Any]:
        return await self.request('PUT', path, **kwargs)

    async def delete(self, path: str, **kwargs) -> Dict[str, Any]:
        return await self.request('DELETE', path, **kwargs)

    async def authenticate(self, username: str, password: str) -> str:
        """Authenticate and return a token."""
        response = await self.post(
            'authenticate',
            data={'username': username, 'password': password},
            just_data=False,
        )

        self.token = response['token']
        return self.token

    async def get_user(self):
        return await self.get('user')

    async def get_user_items(self):
        return await self.get('user/items')

    async def get_user_galleries(self):
        return await self.get('user/galleries')

    async def get_user_devices(self):
        return await self.get('user/devices')

    async def get_user_feedback(self):
        return await self.get('user/feedback')

    async def device_load_gallery(self, device_id: int, gallery_id: int):
        return await self.post(f'devices/{device_id}/galleries/{gallery_id}')

    async def device_load_item(self, device_id: int, item_id: int):
        return await self.post(f'devices/{device_id}/items/{item_id}')

    async def get_device(self, device_id: int):
        return await self.get(f'devices/{device_id}')

    async def get_device_galleries(self, device_id: int):
        return await self.get(f'devices/{device_id}/galleries')

    async def update_device(self, device_id: int, data):
        return await self.put(f'devices/{device_id}', data)

    async def sync_device(self, device_id: int):
        return await self.post(f'devices/{device_id}/sync')

    async def get_item(self, item_id: int):
        return await self.get(f'items/{item_id}')

    async def add_item_to_gallery(self, gallery_id: int, item_id: int):
        return await self.post(f'galleries/{gallery_id}/items/{item_id}')

    async def upload_item(self, image: bytes, image_name: str, just_id: bool = True):
        if (suffix := Path(image_name).suffix.strip('.').lower()) not in _EXTENSIONS:
            raise ValueError(f'{suffix} not supported by meural')

        result = await self.post('items', files={image_name: image}, timeout=60)
        return result['id'] if just_id else result

    async def upload_item_from_url(self, url: str, image_name: Optional[str] = None):
        async with self.session.get(url) as response:
            response.raise_for_status()
            image = await response.read()

        image_name = image_name or urlsplit(url).path.split('/')[-1]

        return await self.upload_item(image=image, image_name=image_name)
