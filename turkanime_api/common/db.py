"""
API işlemleri için modül.
Anime eşleştirme kayıtları ve kullanıcı verileri için REST API'yi yönetir.
"""

import requests
from requests.adapters import HTTPAdapter
import json
from typing import Optional, Dict, List, Tuple, Any
import threading
import time
from datetime import datetime
import uuid


class APIManager:
    """REST API yöneticisi."""

    def __init__(self):
        self.base_url = "https://turkanimeapi.bariskeser.com"
        self.session = requests.Session()
        # Timeout adapter ile ayarla
        adapter = HTTPAdapter(max_retries=3)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """API isteği yapar."""
        try:
            url = f"{self.base_url}{endpoint}"
            headers = {'Content-Type': 'application/json'}

            if method.upper() == 'GET':
                response = self.session.get(url, headers=headers, timeout=10)
            elif method.upper() == 'POST':
                response = self.session.post(url, headers=headers, json=data, timeout=10)
            elif method.upper() == 'PUT':
                response = self.session.put(url, headers=headers, json=data, timeout=10)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, headers=headers, timeout=10)
            else:
                return None

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"API isteği hatası ({method} {endpoint}): {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON parse hatası: {e}")
            return None

    def create_tables(self):
        """API tablolarının hazır olduğunu varsayar."""
        # API tabanlı olduğu için tablo oluşturma gerekmez
        return True

    def save_anime_match(self, source: str, anime_id: str, anime_title: str) -> bool:
        """Anime eşleştirmesini API'ye kaydeder."""
        def worker():
            data = {
                'source': source,
                'anime_id': anime_id,
                'anime_title': anime_title
            }

            result = self._make_request('POST', '/anime-matches', data)
            if result:
                print(f"Anime eşleştirmesi kaydedildi: {source} - {anime_id} - {anime_title}")
            else:
                print(f"Anime eşleştirmesi kaydetme hatası: {source} - {anime_id}")

        # Thread ile çalıştır
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return True

    def get_anime_matches(self, limit: int = 100) -> List[Dict]:
        """Anime eşleştirmelerini API'den getirir."""
        result = self._make_request('GET', f'/anime-matches?limit={limit}')
        if result and isinstance(result, list):
            return result
        return []

    def search_anime_matches(self, query: str) -> List[Dict]:
        """Anime eşleştirmelerinde API üzerinden arama yapar."""
        result = self._make_request('GET', f'/anime-matches/search?q={query}')
        if result and isinstance(result, list):
            return result
        return []

    def save_user_episode_status(self, user_id: str, episode_id: str, watched: bool, downloaded: bool) -> bool:
        """Kullanıcının bölüm durumunu API'ye kaydeder."""
        def worker():
            data = {
                'user_id': user_id,
                'episode_id': episode_id,
                'watched': watched,
                'downloaded': downloaded
            }

            result = self._make_request('POST', '/user/episode-status', data)
            if result:
                print(f"Episode status kaydedildi: {episode_id}")
            else:
                print(f"Episode status kaydetme hatası: {episode_id}")

        # Thread ile çalıştır
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return True

    def get_user_episode_status(self, user_id: str) -> Dict[str, Dict]:
        """Kullanıcının tüm bölüm durumlarını API'den getirir."""
        result = self._make_request('GET', f'/user/{user_id}/episode-status')
        if result and isinstance(result, dict):
            return result
        return {}

    def generate_user_id(self) -> str:
        """Yeni bir kullanıcı kimliği oluşturur."""
        return str(uuid.uuid4())


# Global API yöneticisi
api_manager = APIManager()


def init_database():
    """API bağlantısını başlatır."""
    # API tabanlı olduğu için özel başlatma gerekmez
    print("API bağlantısı hazır")
    return True
