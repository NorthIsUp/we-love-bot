from dataclasses import dataclass
from functools import partial
from typing import Any, Dict, Literal, Optional

import aiohttp
import async_timeout
import requests

from welovebot.lib.cog import Cog

GET = 'GET'
POST = 'POST'


@dataclass
class Meural(Cog):
    class Config:
        USERNAME: str
        PASSWORD: str

    netloc: str = 'api.meural.com'
    version: int = 1
    token: str = ''
    session: requests.Session = requests.Session()

    def __post_init__(self):
        self.url = f'https://{self.netloc}/v{self.version}'

    async def request(
        self,
        method: Literal['GET', 'POST'],
        path: str,
        data: Optional[Dict[str, Any]] = None,
        raise_for_status: bool = True,
        just_data: bool = True,
        timeout: int = 10,
        api_version: int = 3,
        **request_kwargs: Any,
    ) -> Dict:
        url = f'{self.url}/{path}'
        request_kwargs.setdefault('headers', {}).update(
            {
                'Authorization': f'Token {self.token}',
                'x-meural-api-version': str(api_version),
            }
        )

        if data and method == 'get':
            request_kwargs['query'] = data
        elif data:
            request_kwargs['json'] = data

        with async_timeout.timeout(timeout):
            _request = partial(self.session.request, method, url, **request_kwargs)
            response = await self.loop.run_in_executor(None, _request)

            curlit(response)

            if raise_for_status:
                response.raise_for_status()

            return response.json()['data'] if just_data else response.json()

    async def get(self, path, **kwargs) -> Dict:
        for k in ('image', 'data'):
            if k in kwargs:
                raise ValueError(f'{k} is not supported for GET requests')

        if 'image' in kwargs:
            raise ValueError('image is not supported for GET requests')

        return await self.request('GET', path, **kwargs)

    async def post(self, path, **kwargs) -> Dict:
        return await self.request('POST', path, **kwargs)

    async def authenticate(self) -> str:
        """Authenticate and return a token."""
        response = await self.post(
            f'{self.url}/authenticate',
            data={
                'username': self.config_safe['USERNAME'],
                'password': self.config_safe['PASSWORD'],
            },
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

    async def device_load_gallery(self, device_id, gallery_id):
        return await self.post(f'devices/{device_id}/galleries/{gallery_id}')

    async def device_load_item(self, device_id, item_id):
        return await self.post(f'devices/{device_id}/items/{item_id}')

    async def get_device(self, device_id):
        return await self.get(f'devices/{device_id}')

    async def get_device_galleries(self, device_id):
        return await self.get(f'devices/{device_id}/galleries')

    async def update_device(self, device_id, data):
        return await self.request('put', f'devices/{device_id}', data)

    async def sync_device(self, device_id):
        return await self.post(f'devices/{device_id}/sync')

    async def get_item(self, item_id):
        return await self.get(f'items/{item_id}')

    async def upload_item(self, image, image_ext):
        result = await self.post(
            'items',
            image=image,
            image_ext=image_ext,
            files=[('image', (f'image.{ext}', image))],
            timeout=60,
        )
        return result['id']

    async def upload_item_to_gallery(self, image, gallery_id):
        id = await self.upload_item(image)
        return await self.post(f'galleries/{gallery_id}/items/{id}')

    async def upload_item_from_url(self, url: str):
        def _pull_url(url: str) -> bytes:
            response = requests.get(url, stream=True)
            response.raw.decode_content = True
            return response.content

        id = await self.upload_item(_pull_url(url))
        gallery_id = 243290
        return await self.request('POST', f'galleries/{gallery_id}/items/{id}')

    @Cog.on_ready
    async def setup(self):
        print('pre-auth')
        token = await self.authenticate()
        # print(await self.get_user())
        # print(await self.get_user_devices())
        # print(await self.get_user_galleries())
        print(f'meural token {token}')
        await self.upload_item_from_url(
            'https://tinybeans.com/pv/e/407545284/150bb51e-e0cd-4333-a0b9-3c78a0dd1066-o.jpg'
        )
