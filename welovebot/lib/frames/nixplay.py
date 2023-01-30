import json
from dataclasses import dataclass, field
from http.cookies import Morsel
from typing import Dict, Iterable, Optional, Union, cast

import requests
from requests.cookies import RequestsCookieJar

NIXPLAY_API = 'api.nixplay.com'
NIXPLAY_BASE = 'https://app.nixplay.com'
FAKE_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'

SDictT = Dict[str, Union[str, int]]
IdT = Union[str, int]
PhotoT = bytes


@dataclass
class NixPhoto:
    photo_url: str
    thumbnail_url: str = ''
    orientation: int = 0
    caption: str = ''

    def __post_init__(self):
        self.thumbnail_url = self.thumbnail_url or self.photo_url

    def serialize(self) -> SDictT:
        return {
            'photoUrl': self.photo_url,
            'thumbnailUrl': self.thumbnail_url,
            'orientation': self.orientation,  # = 1 if photo["width_o"] < photo["height_o"] else 0
            'caption': self.caption,
        }


@dataclass
class NixPlay:
    csrftok: Optional[str] = None
    cookies: RequestsCookieJar = field(default_factory=RequestsCookieJar)
    session: requests.Session = requests.Session()
    user: str = ''

    @property
    def headers(self) -> Dict[str, str]:
        assert self.user, 'must log in first'
        assert self.csrftok is not None, 'csrf token must be set'

        return {
            'X-CSRFToken': self.csrftok,
            'X-Nixplay-Username': self.user,
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'{NIXPLAY_BASE}/',
            'Origin': f'{NIXPLAY_BASE}',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'User-Agent': FAKE_AGENT,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Content-Type': 'application/json',
        }

    def login(self, user: str, password: str):
        if self.user and self.csrftok:
            return

        self.user = f'{user}@mynixplay.com'

        data = {
            'email': user,
            'password': password,
            'signup_pair': 'no_pair',
            'login_remember': 'false',
        }
        hdr = {
            'Referer': f'{NIXPLAY_BASE}/login',
            'Origin': f'{NIXPLAY_BASE}',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
        }
        r = self.session.post(f'https://{NIXPLAY_API}/www-login/', headers=hdr, data=data)
        # data = dump.dump_all(r)
        # print(data.decode('utf-8'))

        j = json.loads(r.text)
        token = j['token']

        data = {'token': token, 'startPairing': 'false', 'redirectPath': ''}
        hdr = {
            'Referer': f'{NIXPLAY_BASE}/login',
            'Origin': f'{NIXPLAY_BASE}',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-site',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }
        r = self.session.post(
            f'https://{NIXPLAY_API}/v2/www-login-redirect/',
            headers=hdr,
            data=data,
            allow_redirects=False,
        )

        self.cookies = r.cookies

        # save the CSRF token
        self.csrftok = r.cookies['prod.csrftoken']

        return j

    def get_api_v3(self, endpoint: str, params: Optional[SDictT] = None) -> Dict[str, str]:
        u = f'https://{NIXPLAY_API}/v3/{endpoint}'
        r = self.session.get(u, headers=self.headers, params=params or {})
        return json.loads(r.text)

    def post_api_v3(
        self,
        endpoint: str,
        data: Union[SDictT, Iterable[SDictT]],
    ) -> requests.Response:
        u = f'https://{NIXPLAY_API}/v3/{endpoint}'
        r = self.session.post(u, headers=self.headers, data=json.dumps(data))
        return r

    def post_api_v1(
        self,
        endpoint: str,
        data: Union[SDictT, Iterable[SDictT]],
    ) -> requests.Response:
        u = f'https://{NIXPLAY_API}/v1/{endpoint}'
        r = self.session.post(u, headers=self.headers, data=json.dumps(data))
        return r

    def delete_api_v3(self, endpoint: str, params: Optional[SDictT] = None) -> requests.Response:
        u = f'https://{NIXPLAY_API}/v3/{endpoint}'
        r = self.session.delete(u, headers=self.headers, params=params or {})
        return r

    #
    # NixPlay API
    #

    def online_status(self):
        return self.get_api_v3('frame/online-status/')

    @property
    def frames(self) -> Iterable[Dict[str, str]]:
        return self.get_api_v3('frames')

    def frame(self, name: str) -> Optional[Dict[str, str]]:
        for frame in self.frames:
            if frame['name'] == name:
                return frame
        return None

    def frame_settings(self, frame_id: int) -> Dict[str, str]:
        return self.get_api_v3(f'frame/settings/?frame_pk={frame_id}')

    @property
    def playlists(self) -> Iterable[Dict[str, str]]:
        return self.get_api_v3('playlists')

    def playlist(self, name: str):
        for p in self.playlists:
            if p['name'] == name:
                return p

    def get_play_list_slides(self, playlist_id: IdT, offset: int = 0, size: int = 100):
        return self.get_api_v3(f'playlists/{playlist_id}/slides', {'size': size, 'offset': offset})

    def add_photos(self, playlist_id: IdT, *photos: NixPhoto):
        return self.post_api_v3(
            f'playlists/{playlist_id}/items', {'items': [p.serialize() for p in photos]}
        )

    def set_attrs(self, photo_id: IdT, caption):
        self.patch_api_v3(f'pictures/{photo_id}/attrs', {'caption': caption})

    # photos can be a list or a single item
    # def delPlayListPhotos(self, playlist_id: IdT, photos: Union[NixPhoto, Iterable[NixPhoto]]):
    #     params = {'id': photos, 'delPhoto': ''}
    #     return self.delete_api_v3(f'playlists/{playlist_id}/items', params=params)

    # def delPlayListPhotoRange(self, playlist_id, offset, count):
    #  photos = self.getPlayListSlides(playlist_id, offset, count)
    #  ids = [p['playlistItemId'] for p in photos]
    #  return self.delPlayListPhotos(playlist_id, ids)

    # def delPlayList(self, playlist_id: IdT):
    #     return self.delete_api_v3(f'playlists/{playlist_id}/items')  # ?delPhoto=')

    # def updatePlaylist(self, frame_id: IdT, playlist_id: IdT = ''):
    #     # application/x-www-form-urlencoded;
    #     data = {'frame_pk': frame_id, 'slideshow_list': playlist_id, 'operation': 'update'}
    #     return self.post_api_v3(f'playlists/{playlist_id}/items')  # ?delPhoto=')

    # def updateActivities(self):
    #     return self.post_api_v3(f'users/activities', data={})
