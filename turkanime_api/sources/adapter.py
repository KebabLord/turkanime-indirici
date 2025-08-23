from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Any, Dict
import json
from tempfile import NamedTemporaryFile
from os.path import join
import subprocess as sp
import re

from yt_dlp import YoutubeDL

from .animecix import _video_streams


@dataclass
class AdapterAnime:
    slug: str
    title: str


class AdapterVideo:
    """TürkAnime Video arayüzüne minimum uyumlu basit video nesnesi."""

    def __init__(self, bolum: 'AdapterBolum', url: str, label: Optional[str] = None):
        self.bolum = bolum
        self._url = url
        self.label = label
        self.player = "ANIMECIX"
        self._info: Optional[Dict[str, Any]] = None
        self.is_supported = True
        self._is_working: Optional[bool] = None
        self._resolution: Optional[int] = None
        self.ydl_opts = {
            'logger': None,
            'quiet': True,
            'ignoreerrors': 'only_download',
            'retries': 5,
            'fragment_retries': 10,
            'restrictfilenames': True,
            'nocheckcertificate': True,
            'concurrent_fragment_downloads': 5,
        }

    @property
    def url(self) -> str:
        return self._url

    @property
    def info(self):
        if self._info is None:
            with YoutubeDL(self.ydl_opts) as ydl:
                raw_info = ydl.extract_info(self.url, download=False)
                info = ydl.sanitize_info(raw_info)
            if not info:
                self._info = {}
            else:
                if "direct" in info:
                    del info["direct"]
                if info.get("video_ext") == "html":
                    info = None
                self._info = info
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
        with YoutubeDL(opts) as ydl:
            ydl.download_with_info_file(tmp.name)

    def oynat(self, dakika_hatirla=False, izlerken_kaydet=False, mpv_opts=None):
        assert self.is_working, "Video çalışmıyor."
        if mpv_opts is None:
            mpv_opts = []
        with NamedTemporaryFile("w", delete=False) as tmp:
            json.dump(self.info, tmp)
        cmd = [
            "mpv",
            "--no-input-terminal",
            "--msg-level=all=error",
            "--script-opts=ytdl_hook-ytdl_path=yt-dlp,ytdl_hook-try_ytdl_first=yes",
            "--ytdl-raw-options=load-info-json=" + tmp.name,
            "ytdl://" + self.bolum.slug,
        ]
        if dakika_hatirla:
            mpv_opts.append("--save-position-on-quit")
        if izlerken_kaydet:
            mpv_opts.append("--stream-record")
        for opt in mpv_opts:
            cmd.insert(1, opt)
        return sp.run(cmd, text=True, stdout=sp.PIPE, stderr=sp.PIPE)

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
                        self._resolution = max(fmts, key=lambda x: x.get("height") or 0).get("height") or 0
                    else:
                        t = max(fmts, key=lambda x: (x.get("height") or 0, x.get("tbr") or 0))
                        self._resolution = (t.get("height") or (720 if (t.get("tbr") or 0) > 1500 else 480)) or 0
                except Exception:
                    self._resolution = 0
            else:
                # Label'dan tahmin
                m = re.findall(r"(\d{3,4})p", str(self.label or ""))
                self._resolution = int(m[0]) if m else 0
            # mpv ile son çare çözünürlük tespiti
            if not self._resolution:
                try:
                    import subprocess as _sp
                    cmd = [
                        "mpv", "--no-config", "--no-audio", "--no-video",
                        "--frames=1", "--really-quiet",
                        "--term-playing-msg=${video-params/w}x${video-params/h}",
                        self.url,
                    ]
                    res = _sp.run(cmd, text=True, stdout=_sp.PIPE, stderr=_sp.PIPE, timeout=10)
                    out = (res.stdout or "") + (res.stderr or "")
                    mm = re.findall(r"(\d{3,4})x(\d{3,4})", out)
                    if mm:
                        self._resolution = int(mm[-1][1])
                except Exception:
                    pass
        return self._resolution or 0


class AdapterBolum:
    def __init__(self, url: str, title: str, anime: AdapterAnime):
        self.url = url
        self._title = title
        self.anime = anime
        # Basit, güvenli slug
        safe = re.sub(r"[^a-z0-9\-]+", "-", title.lower().replace(" ", "-"))[:60]
        self.slug = f"cix-{safe}"

    @property
    def title(self):
        return self._title

    @property
    def fansubs(self):
        # AnimeciX tarafında fansub konsepti kullanılmıyor
        return []

    def best_video(self, by_res=True, by_fansub=None, default_res=600, callback=lambda x: None, early_subset: int = 8):
        # AnimeciX embed path üzerinden stream listesi
        callback({"current": 0, "total": 1, "player": "ANIMECIX", "status": "üstbilgi çekiliyor"})
        streams = _video_streams(self.url)
        if not streams:
            callback({"current": 1, "total": 1, "player": "ANIMECIX", "status": "hiçbiri çalışmıyor"})
            return None

        def parse_res(label: str) -> int:
            m = re.findall(r"(\d{3,4})p", label or "")
            return int(m[0]) if m else default_res

        picked = max(streams, key=lambda s: parse_res(s.get("label") or "0p")) if by_res else streams[0]
        vid = AdapterVideo(self, picked.get("url"), picked.get("label"))
        if vid.is_working:
            callback({"current": 1, "total": 1, "player": "ANIMECIX", "status": "çalışıyor"})
            return vid
        callback({"current": 1, "total": 1, "player": "ANIMECIX", "status": "çalışmıyor"})
        return None
