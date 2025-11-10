"""
Anizle.com için API istemcisi.
Bu modül, turkanime-server üzerinde çalışan ve Selenium kazıması yapan API'ye isteklerde bulunur.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import json
import requests

# Sunucu adresi ayarlanabilir olmalı
SERVER_URL = "https://turkanimeapi.bariskeser.com" # Uzak sunucu adresi

def _api_get(endpoint: str, params: Optional[Dict[str, Any]] = None, timeout: int = 60) -> Any:
    """API sunucusuna GET isteği gönderir ve JSON yanıtını döndürür."""
    try:
        response = requests.get(f"{SERVER_URL}{endpoint}", params=params, timeout=timeout)
        response.raise_for_status()  # HTTP 2xx olmayan durumlar için hata fırlat
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API isteği sırasında hata oluştu: {e}")
        return None # veya boş bir liste/dict

def search_anizle(query: str, limit: int = 20, timeout: int = 60) -> List[Tuple[str, str]]:
    """Anizle üzerinde arama yapmak için API'yi kullanır."""
    params = {'q': query, 'limit': limit}
    results = _api_get("/anizle/search", params=params, timeout=timeout)
    return results if isinstance(results, list) else []

def get_anime_episodes(slug: str, timeout: int = 60) -> List[Tuple[str, str]]:
    """Bir animenin bölümlerini getirmek için API'yi kullanır."""
    results = _api_get(f"/anizle/episodes/{slug}", timeout=timeout)
    return results if isinstance(results, list) else []

def get_episode_streams(episode_slug: str, timeout: int = 60) -> List[Dict[str, str]]:
    """Bir bölümün video stream'lerini getirmek için API'yi kullanır."""
    results = _api_get(f"/anizle/streams/{episode_slug}", timeout=timeout)
    return results if isinstance(results, list) else []


@dataclass
class AnizleEpisode:
    title: str
    url: str

    def streams(self, timeout: int = 60) -> List[Dict[str, str]]:
        return get_episode_streams(self.url, timeout=timeout)


@dataclass
class AnizleAnime:
    slug: str
    title: str

    @property
    def episodes(self) -> List[AnizleEpisode]:
        eps: List[AnizleEpisode] = []
        episodes_data = get_anime_episodes(self.slug)
        if episodes_data:
            for slug, label in episodes_data:
                eps.append(AnizleEpisode(title=label, url=slug))
        return eps


__all__ = [
    "AnizleAnime",
    "AnizleEpisode",
    "get_anime_episodes",
    "get_episode_streams",
    "search_anizle",
]
