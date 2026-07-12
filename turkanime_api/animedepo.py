"""
AnimeDepo sağlayıcı.

Bu modül AnimeDepo kullanarak script'in kullanabileceği Anime, Bolum, Video formatlarını
expose eder. Bu sayede kolaylıkla turkanime_api.Bolum yerine animedepo.Bolum kullanılabilir.
    from turkanime_api import animedepo
    anime = animedepo.Anime("inferno-cop")
"""
from curl_cffi import requests

from .objects import Anime as BaseAnime
from .objects import Bolum as BaseBolum
from .objects import Video as BaseVideo
from .objects import LogHandler
from . import bypass


BASE_URL = "https://gitlab.com/AnimeDepo/animedepo/-/raw/master"
_dizin = None


def fetch_json(path):
    """AnimeDepo JSON dosyasını getir."""
    url = BASE_URL + "/" + path.lstrip("/")
    response = requests.get(url,timeout=10)
    response.raise_for_status()
    return response.json()


def dizin():
    """AnimeDepo dizin.json dosyasını cache'li döndür."""
    global _dizin
    if _dizin is None:
        _dizin = fetch_json("dizin.json")
    return _dizin


def dizin_anime(slug):
    """Dizin cache'i içinden slug'a ait metadata'yı döndür."""
    for anime_grubu in dizin().get("index",{}).values():
        if slug in anime_grubu:
            return anime_grubu[slug]
    return {}


class Anime(BaseAnime):
    """AnimeDepo üstünden anime bilgisini temsil eder."""

    def fetch_info(self):
        """animeler/{slug}/info.json dosyasını self.info içine aktar."""
        data = fetch_json(f"animeler/{self.slug}/info.json")
        self.info.update(data)
        self._title = data.get("title") or data.get("Başlık") or dizin_anime(self.slug).get("title") or self._title

    def get_bolum_listesi(self):
        """AnimeDepo bölüm listesini [(slug,title),] formatında döndür."""
        data = fetch_json(f"animeler/{self.slug}/bolumler.json")
        return [(slug,title) for slug,title in data]

    @staticmethod
    def get_anime_listesi():
        """AnimeDepo anime listesini [(slug,title),] formatında döndür."""
        liste = []
        for anime_grubu in dizin().get("index",{}).values():
            for slug,anime in anime_grubu.items():
                liste.append((slug,anime["title"]))
        return liste

    @staticmethod
    def arama_yap(query):
        """AnimeDepo arama sonucunu [(slug,title),] formatında döndür."""
        # TODO: AnimeDepo arama index formatına göre doldur.
        raise NotImplementedError

    @property
    def bolumler(self):
        """Bölümleri provider'a ait Bolum sınıfıyla yarat."""
        if not self._bolumler:
            for slug,title in self.get_bolum_listesi():
                self._bolumler.append(
                    Bolum(
                        slug=slug,
                        title=title,
                        anime=self,
                        parse_fansubs=self.parse_fansubs))
        return self._bolumler


class Bolum(BaseBolum):
    """AnimeDepo üstünden bölüm bilgisini temsil eder."""

    @property
    def html(self):
        """AnimeDepo JSON tabanlıysa HTML kullanılmaz."""
        raise NotImplementedError

    @property
    def fansubs(self):
        """Bölümde bulunan fansub listesini döndür."""
        if not self._fansubs:
            self.get_videos()
            self._fansubs = list(dict.fromkeys(v.fansub for v in self._videos if v.fansub))
        return self._fansubs

    def get_videos(self):
        """Bölüm videolarını provider'a ait Video sınıfıyla yarat."""
        if self.anime is None:
            raise ValueError("Bölüm objesi anime objesinden yaratılmalıdır.")
        self._videos = []
        data = fetch_json(f"animeler/{self.anime.slug}/{self.slug}.json")
        for item in data:
            if item.get("alive") is False:
                continue
            video_path = item.get("mask") or item.get("path") or item.get("url")
            if not video_path:
                continue
            self._videos.append(Video(
                self,
                video_path,
                player=item.get("player"),
                fansub=item.get("fansub"),
                mask=item.get("mask"),
                url=item.get("url")))
        return self._videos


class Video(BaseVideo):
    """AnimeDepo üstünden video bilgisini temsil eder."""

    def __init__(self,bolum,path,player=None,fansub=None,mask=None,url=None,log_handler=LogHandler):
        super().__init__(bolum,path,player=player,fansub=fansub,log_handler=log_handler)
        self.mask = mask
        self._url = url

    @property
    def url(self):
        """AnimeDepo url veriyorsa direkt kullan; mask/path varsa çöz."""
        if self._url is None and self.mask:
            bypass.fetch(None)
            mask = self.mask if self.mask.startswith("http") else bypass.BASE_URL + self.mask
            self._url = bypass.unmask_real_url(mask, video=self)
            return self._url
        return super().url
