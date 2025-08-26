"""AnimeciX kaynağı (minimal Python port)

Bu modül, AnimeciX API uçlarından arama ve bölüm/izleme verilerini çeker.
Mevcut `objects.Anime/Bolum/Video` yapısına dokunmamak için, yalnızca
harici arama/episode/watch listesi sağlar; indirme/oynatma yine yt-dlp/mpv ile.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import json
import re
from urllib.parse import urlparse, parse_qs, quote, urlsplit, urlunsplit

import urllib.request


BASE_URL = "https://animecix.tv/"
ALT_URL = "https://mangacix.net/"
HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
VIDEO_PLAYERS = ["tau-video.xyz", "sibnet"]


def _http_get(url: str) -> bytes:
    # Non-ASCII pathleri ASCII'ye uygun hale getirmek için yüzde-encode et
    sp = urlsplit(url)
    safe_path = quote(sp.path, safe="/:%@")
    # Query kısmı zaten ASCII ise aynen kullan; aksi durumda çağıran taraf urlencode etmelidir
    safe_url = urlunsplit((sp.scheme, sp.netloc, safe_path, sp.query, sp.fragment))
    req = urllib.request.Request(safe_url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def search_animecix(query: str) -> List[Tuple[str, str]]:
    # Boşluk -> '-' ve non-ASCII karakterleri encode et
    q = (query or "").strip().replace(" ", "-")
    q_enc = quote(q, safe="-")
    url = f"{BASE_URL}secure/search/{q_enc}?type=&limit=20"
    data = json.loads(_http_get(url))
    results = []
    res = data.get("results") or []
    for item in res:
        name = item.get("name")
        _id = item.get("id")
        if name is None or _id is None:
            continue
        results.append((str(_id), str(name)))
    return results


def _seasons_for_title(title_id: int) -> List[int]:
    url = f"{ALT_URL}secure/related-videos?episode=1&season=1&titleId={title_id}&videoId=637113"
    data = json.loads(_http_get(url))
    videos = data.get("videos") or []
    if not videos:
        return []
    title = (videos[0] or {}).get("title") or {}
    seasons = title.get("seasons") or []
    return list(range(len(seasons)))


def _episodes_for_title(title_id: int) -> List[Dict[str, Any]]:
    episodes: List[Dict[str, Any]] = []
    seen = set()
    for sidx in _seasons_for_title(title_id):
        url = f"{ALT_URL}secure/related-videos?episode=1&season={sidx+1}&titleId={title_id}&videoId=637113"
        data = json.loads(_http_get(url))
        for v in data.get("videos", []):
            name = v.get("name")
            ep_url = v.get("url")
            if not name or not ep_url:
                continue
            if name in seen:
                continue
            episodes.append({"name": name, "url": ep_url, "season_num": v.get("season_num")})
            seen.add(name)
    return episodes


def _video_streams(embed_path: str) -> List[Dict[str, str]]:
    # BASE_URL + embed path'e gidip yönlendirilmiş URL'den player id/vid al
    import http.client
    import ssl
    # Embed path non-ASCII içerebilir; güvenle encode et
    full = f"{BASE_URL}{quote(embed_path, safe='/:?=&')}"
    # Basit urllib ile final URL
    resp = urllib.request.urlopen(urllib.request.Request(full, headers=HEADERS))
    final_url = resp.geturl()
    p = urlparse(final_url)
    parts = p.path.strip("/").split("/")
    if len(parts) < 2:
        return []
    embed_id = parts[1] if parts[0] == "embed" else parts[0]
    qs = parse_qs(p.query)
    vid = (qs.get("vid") or [None])[0]
    if not embed_id or not vid:
        return []
    api = f"https://{VIDEO_PLAYERS[0]}/api/video/{embed_id}?vid={vid}"
    data = json.loads(_http_get(api))
    out: List[Dict[str, str]] = []
    for u in data.get("urls", []):
        label = u.get("label")
        url = u.get("url")
        if label and url:
            out.append({"label": label, "url": url})
    return out


@dataclass
class CixEpisode:
    title: str
    url: str


@dataclass
class CixAnime:
    """AnimeciX başlığı.

    Not: Bu sınıf, yalnızca isim ve bölümleri sağlar. Oynatma/indirme için
    mevcut Video/Bolum akışı kullanılmaya devam edilir.
    """
    id: int
    title: str

    @property
    def episodes(self) -> List[CixEpisode]:
        eps = _episodes_for_title(self.id)
        out: List[CixEpisode] = []
        for i, e in enumerate(eps):
            out.append(CixEpisode(title=e.get("name") or f"Bölüm {i+1}", url=e.get("url") or ""))
        return out
