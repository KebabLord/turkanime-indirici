from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Any, Dict
import json
from tempfile import NamedTemporaryFile
from os.path import join
import subprocess as sp
import re
import unicodedata

from yt_dlp import YoutubeDL

from .animecix import _video_streams
from ..common.utils import get_ydl_opts, get_video_resolution_mpv, extract_video_info
from turkanime_api.sources.animecix import search_animecix
from turkanime_api.objects import Anime


def _slugify(text: str) -> str:
    """Basit ve güvenli bir slug üretici: ASCII'ye indirger,
    boşlukları '-' yapar, gereksizleri temizler."""
    if not text:
        return ""
    # Unicode -> ASCII transliterasyon
    t = unicodedata.normalize("NFKD", str(text))
    t = t.encode("ascii", "ignore").decode("ascii")
    t = t.lower()
    t = re.sub(r"\s+", "-", t)
    t = re.sub(r"[^a-z0-9\-]", "-", t)
    t = re.sub(r"-+", "-", t).strip("-")
    return t[:80]


@dataclass
class AdapterAnime:
    slug: str
    title: str

    def __post_init__(self):
        # Eğer slug sayı/ID ise ya da boşsa, başlıktan güvenli bir slug üret.
        raw = (self.slug or "").strip()
        if not raw or raw.isdigit() or not re.search(r"[a-zA-Z]", raw):
            self.slug = _slugify(self.title)


class AdapterVideo:
    """TürkAnime Video arayüzüne minimum uyumlu basit video nesnesi."""

    def __init__(self, bolum: 'AdapterBolum', url: Optional[str], label: Optional[str] = None):
        self.bolum = bolum
        self._url = url or ""
        self.label = label
        self.player = "ANIMECIX"
        self._info: Optional[Dict[str, Any]] = None
        self.is_supported = True
        self._is_working: Optional[bool] = None
        self._resolution: Optional[int] = None
        self.ydl_opts = get_ydl_opts()

    @property
    def url(self) -> str:
        return self._url

    @property
    def info(self) -> Optional[Dict[str, Any]]:
        if self._info is None:
            info = extract_video_info(self.url, self.ydl_opts)
            if not info:
                self._info = {}
            else:
                # info'nun Dict[str, Any] olduğunu garanti edelim
                if isinstance(info, dict):
                    if "direct" in info:
                        del info["direct"]
                    if info.get("video_ext") == "html":
                        self._info = None
                    else:
                        self._info = info
                else:
                    self._info = {}
        return self._info

    @property
    def is_working(self) -> bool:
        if self._is_working is None:
            try:
                self._is_working = self.info not in (None, {})
            except Exception:
                self._is_working = False
        return self._is_working

    @is_working.setter
    def is_working(self, value: bool):
        self._is_working = value

    def indir(self, callback=None, output=""):
        assert self.is_working, "Video çalışmıyor."
        seri_slug = self.bolum.anime.slug if getattr(self.bolum, 'anime', None) else ""
        out_tmpl_dir = join(output, seri_slug, self.bolum.slug)
        opts = self.ydl_opts.copy()
        if callback:
            opts['progress_hooks'] = [callback]
        opts['outtmpl'] = {'default': out_tmpl_dir + r'.%(ext)s'}
        with NamedTemporaryFile("w", delete=False) as tmp:
            json.dump(self.info, tmp)
        with YoutubeDL(opts) as ydl:  # type: ignore
            ydl.download_with_info_file(tmp.name)

    def get(self, key, default=None):
        """Dictionary-like get method for compatibility."""
        if key == 'url':
            return self.url
        elif key == 'label':
            return self.label
        elif key == 'player':
            return self.player
        return default

    @property
    def resolution(self) -> int:
        if self._resolution is None:
            info = self.info or {}
            res = info.get("resolution")
            if res:
                m = re.findall(r"(\d{3,4})p", str(res))
                if m:
                    self._resolution = int(m[0])
                    return self._resolution
            fmts = info.get("formats") or []
            if fmts:
                try:
                    if "height" in (fmts[0] or {}):
                        self._resolution = max(
                            fmts,
                            key=lambda x: x.get("height") or 0
                        ).get("height") or 0
                    else:
                        t = max(fmts, key=lambda x: (x.get("height") or 0, x.get("tbr") or 0))
                        self._resolution = (
                            t.get("height") or
                            (720 if (t.get("tbr") or 0) > 1500 else 480)
                        ) or 0
                except Exception:
                    self._resolution = 0
            else:
                # Label'dan tahmin
                m = re.findall(r"(\d{3,4})p", str(self.label or ""))
                self._resolution = int(m[0]) if m else 0
            # mpv ile son çare çözünürlük tespiti
            if not self._resolution:
                self._resolution = get_video_resolution_mpv(self.url) or 0
        return self._resolution or 0


class AdapterBolum:
    def __init__(self, url: Optional[str], title: str, anime: AdapterAnime):
        self.url = url
        self._title = title
        self.anime = anime
        # TürkAnime ile uyumlu: animeadı-bolumadı (klasör: anime.slug, dosya adı: animeadı-bolumadı)
        self.slug = _slugify(f"{anime.title}-{title}" if anime else title)

    @property
    def title(self):
        return self._title

    @property
    def fansubs(self):
        # AnimeciX tarafında fansub konsepti kullanılmıyor
        return []

    def best_video(
        self,
        by_res=True,
        by_fansub=None,
        default_res=600,
        callback=lambda x: None,
        early_subset: int = 8
    ):
        # URL kontrolü
        if not self.url:
            callback({"current": 1, "total": 1, "player": "ANIMECIX", "status": "URL bulunamadı"})
            return None

        # AnimeciX embed path üzerinden stream listesi
        callback({"current": 0, "total": 1, "player": "ANIMECIX", "status": "üstbilgi çekiliyor"})
        streams = _video_streams(self.url)
        if not streams:
            callback({
                "current": 1,
                "total": 1,
                "player": "ANIMECIX",
                "status": "hiçbiri çalışmıyor"
            })
            return None

        def parse_res(label: str) -> int:
            m = re.findall(r"(\d{3,4})p", label or "")
            return int(m[0]) if m else default_res

        picked = max(
            streams,
            key=lambda s: parse_res(s.get("label") or "0p")
        ) if by_res else streams[0]
        video_url = picked.get("url")
        if not video_url:
            callback({
                "current": 1,
                "total": 1,
                "player": "ANIMECIX",
                "status": "video URL bulunamadı"
            })
            return None

        vid = AdapterVideo(self, video_url, picked.get("label"))
        if vid.is_working:
            callback({"current": 1, "total": 1, "player": "ANIMECIX", "status": "çalışıyor"})
            return vid
        callback({"current": 1, "total": 1, "player": "ANIMECIX", "status": "çalışmıyor"})
        return None


class SearchEngine:
    def __init__(self):
        from ..common.adapters import AniListAdapter, TurkAnimeAdapter, AnimeciXAdapter
        self.adapters = {
            "AniList": AniListAdapter(),
            "TürkAnime": TurkAnimeAdapter(),
            "AnimeciX": AnimeciXAdapter()
        }
    
    def search_all_sources(self, query, limit_per_source=10):
        results = {}
        # Tüm adapter'ları kullanarak arama yap
        for source_name, adapter in self.adapters.items():
            try:
                results[source_name] = adapter.search_anime(query, limit=limit_per_source)
            except Exception:
                results[source_name] = []
        
        return results
    
    def get_adapter(self, source_name):
        """Kaynak adına göre adapter döndürür."""
        return self.adapters.get(source_name)
