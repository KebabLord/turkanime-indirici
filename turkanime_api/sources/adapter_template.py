"""
Anime Provider Adapter Template

Bu dosya, yeni anime sağlayıcıları eklemek için kullanılan template'i içerir.
Yeni bir sağlayıcı eklemek için bu dosyayı kopyalayıp düzenleyin.

Adımlar:
1. Bu dosyayı kopyalayın: cp adapter_template.py my_provider.py
2. Sınıf adını değiştirin: class MyProviderAdapter
3. PROVIDER_CONFIG'i sağlayıcınıza göre düzenleyin
4. Gerekli metodları implement edin
5. sources/__init__.py'ye import ekleyin
6. sources/__init__.py'deki PROVIDERS listesine ekleyin
"""

from typing import List, Dict, Optional, Any
from abc import ABC, abstractmethod
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
import re
import time

from ..objects import Anime, Bolum


class TemplateAnimeAdapter:
    """Anime sağlayıcıları için base adapter sınıfı."""

    # Sağlayıcı konfigürasyonu
    PROVIDER_CONFIG = {
        "name": "Template Provider",  # Sağlayıcının adı
        "base_url": "https://example.com",  # Ana URL
        "search_url": "https://example.com/search?q={query}",  # Arama URL'si
        "anime_url": "https://example.com/anime/{anime_id}",  # Anime detay URL'si
        "supported_resolutions": ["360p", "480p", "720p", "1080p"],  # Desteklenen çözünürlükler
        "rate_limit": 1,  # Saniye cinsinden istek limiti
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",  # User agent
        "timeout": 10,  # İstek timeout'u
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.PROVIDER_CONFIG['user_agent']
        })
        self.last_request = 0

    def _rate_limit_wait(self):
        """Rate limit kontrolü."""
        elapsed = time.time() - self.last_request
        if elapsed < self.PROVIDER_CONFIG['rate_limit']:
            time.sleep(self.PROVIDER_CONFIG['rate_limit'] - elapsed)
        self.last_request = time.time()

    def _make_request(self, url: str, method: str = 'GET', **kwargs) -> Optional[requests.Response]:
        """Rate limited HTTP isteği."""
        self._rate_limit_wait()
        try:
            response = self.session.request(method, url,
                                          timeout=self.PROVIDER_CONFIG['timeout'],
                                          **kwargs)
            response.raise_for_status()
            return response
        except Exception as e:
            print(f"İstek hatası ({url}): {e}")
            return None

    @abstractmethod
    def search_anime(self, query: str) -> List[Dict[str, Any]]:
        """
        Anime arama işlemi.

        Args:
            query: Arama sorgusu

        Returns:
            Anime listesi:
            [
                {
                    "title": "Anime Adı",
                    "url": "https://example.com/anime/123",
                    "image": "https://example.com/image.jpg",  # Opsiyonel
                    "year": 2023,  # Opsiyonel
                    "score": 8.5,  # Opsiyonel
                    "provider_data": {...}  # Sağlayıcıya özel veriler
                },
                ...
            ]
        """
        pass

    @abstractmethod
    def get_anime_details(self, anime_url: str) -> Optional[Dict[str, Any]]:
        """
        Anime detaylarını getir.

        Args:
            anime_url: Anime URL'si

        Returns:
            Anime detayları:
            {
                "title": "Anime Adı",
                "description": "Anime açıklaması",
                "image": "https://example.com/image.jpg",
                "genres": ["Aksiyon", "Macera"],
                "year": 2023,
                "episodes": 24,
                "status": "Tamamlandı",  # veya "Devam Ediyor"
                "score": 8.5,
                "provider_data": {...}
            }
        """
        pass

    @abstractmethod
    def get_episodes(self, anime_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Anime bölümlerini getir.

        Args:
            anime_data: get_anime_details'ten dönen veri

        Returns:
            Bölüm listesi:
            [
                {
                    "title": "Bölüm 1",
                    "episode_number": 1,
                    "url": "https://example.com/watch/123",
                    "thumbnail": "https://example.com/thumb.jpg",  # Opsiyonel
                    "duration": 1440,  # Saniye cinsinden, opsiyonel
                    "provider_data": {...}
                },
                ...
            ]
        """
        pass

    @abstractmethod
    def get_video_urls(self, episode_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Bölümün video URL'lerini getir.

        Args:
            episode_data: get_episodes'ten dönen bölüm verisi

        Returns:
            Video URL'leri:
            [
                {
                    "url": "https://example.com/video.mp4",
                    "quality": "720p",
                    "format": "mp4",
                    "size": 1073741824,  # Byte cinsinden, opsiyonel
                    "provider_data": {...}
                },
                ...
            ]
        """
        pass

    def create_anime_object(self, anime_data: Dict[str, Any]) -> Anime:
        """Adapter verisinden Anime objesi oluştur."""
        # Anime objesi için gerekli slug oluştur
        slug = self._create_slug(anime_data.get('title', 'bilinmeyen-anime'))

        anime = Anime(slug)

        # Info sözlüğünü güncelle
        anime.info["Özet"] = anime_data.get('description', '')
        anime.info["Resim"] = anime_data.get('image', '')
        anime.info["Anime Türü"] = anime_data.get('genres', [])
        anime.info["Bölüm Sayısı"] = anime_data.get('episodes', 0)
        anime.info["Puanı"] = anime_data.get('score', 0.0)

        # Başlık ayarla
        if anime.title is None:
            anime.title = anime_data.get('title', 'Bilinmeyen Anime')

        return anime

    def create_episode_object(self, episode_data: Dict[str, Any], anime: Anime) -> Bolum:
        """Adapter verisinden Bolum objesi oluştur."""
        # Bölüm için gerekli slug oluştur
        slug = self._create_slug(
            episode_data.get('title', f"bolum-{episode_data.get('episode_number', 0)}")
        )

        bolum = Bolum(
            slug=slug,
            anime=anime,
            title=episode_data.get('title', f"Bölüm {episode_data.get('episode_number', 0)}")
        )

        return bolum

    def _create_slug(self, title: str) -> str:
        """Başlıktan slug oluştur."""
        # Türkçe karakterleri dönüştür
        title = title.lower()
        title = re.sub(r'ğ', 'g', title)
        title = re.sub(r'ü', 'u', title)
        title = re.sub(r'ş', 's', title)
        title = re.sub(r'ı', 'i', title)
        title = re.sub(r'ö', 'o', title)
        title = re.sub(r'ç', 'c', title)

        # Özel karakterleri kaldır
        title = re.sub(r'[^a-z0-9\s-]', '', title)
        title = re.sub(r'\s+', '-', title.strip())

        return title

    def is_available(self) -> bool:
        """Sağlayıcının mevcut olup olmadığını kontrol et."""
        try:
            response = self._make_request(self.PROVIDER_CONFIG['base_url'])
            return response is not None and response.status_code == 200
        except:
            return False


class ExampleAnimeAdapter:
    """
    Template anime adapter implementation.

    Bu sınıfı kendi sağlayıcınız için düzenleyin.
    """

    PROVIDER_CONFIG = {
        "name": "Template Provider",
        "base_url": "https://example.com",
        "search_url": "https://example.com/search?q={query}",
        "anime_url": "https://example.com/anime/{anime_id}",
        "supported_resolutions": ["360p", "480p", "720p", "1080p"],
        "rate_limit": 1,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "timeout": 10,
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.PROVIDER_CONFIG['user_agent']
        })
        self.last_request = 0

    def _rate_limit_wait(self):
        """Rate limit kontrolü."""
        elapsed = time.time() - self.last_request
        if elapsed < self.PROVIDER_CONFIG['rate_limit']:
            time.sleep(self.PROVIDER_CONFIG['rate_limit'] - elapsed)
        self.last_request = time.time()

    def _make_request(self, url: str, method: str = 'GET', **kwargs) -> Optional[requests.Response]:
        """Rate limited HTTP isteği."""
        self._rate_limit_wait()
        try:
            response = self.session.request(method, url,
                                          timeout=self.PROVIDER_CONFIG['timeout'],
                                          **kwargs)
            response.raise_for_status()
            return response
        except Exception as e:
            print(f"İstek hatası ({url}): {e}")
            return None

    def search_anime(self, query: str) -> List[Dict[str, Any]]:
        """Anime arama işlemi - IMPLEMENT ME."""
        search_url = self.PROVIDER_CONFIG['search_url'].format(query=query)
        response = self._make_request(search_url)

        if not response:
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        results = []

        # Arama sonuçlarını parse et
        # Bu kısmı sağlayıcınızın HTML yapısına göre düzenleyin
        anime_items = soup.find_all('div', class_='anime-item')  # Örnek selector

        for item in anime_items:
            try:
                title_elem = item.find('h3', class_='anime-title')
                url_elem = item.find('a', class_='anime-link')
                image_elem = item.find('img', class_='anime-image')

                if title_elem and url_elem:
                    anime_data = {
                        "title": title_elem.text.strip(),
                        "url": url_elem['href'],
                        "image": image_elem['src'] if image_elem else None,
                        "provider_data": {
                            "item_id": item.get('data-id'),
                            "search_query": query
                        }
                    }
                    results.append(anime_data)

            except Exception as e:
                print(f"Anime parse hatası: {e}")
                continue

        return results

    def get_anime_details(self, anime_url: str) -> Optional[Dict[str, Any]]:
        """Anime detaylarını getir - IMPLEMENT ME."""
        response = self._make_request(anime_url)

        if not response:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        try:
            # Ana bilgileri al
            title_elem = soup.find('h1', class_='anime-title')
            desc_elem = soup.find('div', class_='anime-description')
            image_elem = soup.find('img', class_='anime-poster')

            # Ek bilgileri al
            info_elem = soup.find('div', class_='anime-info')
            # Image URL'yi güvenli şekilde al
            image_url = ""
            if isinstance(image_elem, Tag):
                image_url = image_elem.get('src', '') or ''
            else:
                image_url = ""

            anime_data = {
                "title": title_elem.text.strip() if title_elem else "Bilinmeyen Anime",
                "description": desc_elem.text.strip() if desc_elem else "",
                "image": image_url,
                "genres": [],
                "year": None,
                "episodes": 0,
                "status": "Bilinmiyor",
                "score": None,
                "provider_data": {
                    "anime_url": anime_url,
                    "parsed_at": time.time()
                }
            }

            # Info elementinden detayları parse et
            if info_elem:
                # Bu kısmı sağlayıcınızın yapısına göre düzenleyin
                year_match = re.search(r'(\d{4})', info_elem.text)
                if year_match:
                    anime_data["year"] = int(year_match.group(1))

                episodes_match = re.search(r'(\d+)\s*Bölüm', info_elem.text)
                if episodes_match:
                    anime_data["episodes"] = int(episodes_match.group(1))

            return anime_data

        except Exception as e:
            print(f"Anime detay parse hatası: {e}")
            return None

    def get_episodes(self, anime_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Anime bölümlerini getir - IMPLEMENT ME."""
        anime_url = anime_data.get('provider_data', {}).get('anime_url')
        if not anime_url:
            return []

        response = self._make_request(anime_url)
        if not response:
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        episodes = []

        # Bölüm listesini parse et
        episode_items = soup.find_all('div', class_='episode-item')  # Örnek selector

        for item in episode_items:
            try:
                title_elem = item.find('h4', class_='episode-title')
                url_elem = item.find('a', class_='episode-link')
                number_elem = item.find('span', class_='episode-number')

                if title_elem and url_elem:
                    # Bölüm numarasını çıkar
                    episode_number = 1
                    if number_elem:
                        number_match = re.search(r'(\d+)', number_elem.text)
                        if number_match:
                            episode_number = int(number_match.group(1))
                    else:
                        # Başlıktan çıkar
                        number_match = re.search(r'Bölüm\s*(\d+)', title_elem.text, re.IGNORECASE)
                        if number_match:
                            episode_number = int(number_match.group(1))

                    episode_data = {
                        "title": title_elem.text.strip(),
                        "episode_number": episode_number,
                        "url": url_elem['href'],
                        "thumbnail": "",
                        "duration": None,
                        "provider_data": {
                            "episode_id": item.get('data-id'),
                            "anime_url": anime_url
                        }
                    }
                    episodes.append(episode_data)

            except Exception as e:
                print(f"Bölüm parse hatası: {e}")
                continue

        # Bölümleri bölüm numarasına göre sırala
        episodes.sort(key=lambda x: x['episode_number'])

        return episodes

    def get_video_urls(self, episode_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Bölümün video URL'lerini getir - IMPLEMENT ME."""
        episode_url = episode_data.get('url')
        if not episode_url:
            return []

        response = self._make_request(episode_url)
        if not response:
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        video_urls = []

        try:
            # Video kaynaklarını bul
            # Bu kısmı sağlayıcınızın video oynatma yapısına göre düzenleyin
            video_sources = soup.find_all('source')  # HTML5 video
            for source in video_sources:
                video_url = source.get('src')
                if video_url:
                    # Kalite bilgisini çıkar
                    quality = "720p"  # Default
                    if 'quality' in source.attrs:
                        quality = source['quality']
                    elif 'data-quality' in source.attrs:
                        quality = source['data-quality']

                    video_data = {
                        "url": video_url,
                        "quality": quality,
                        "format": self._get_video_format(video_url),
                        "size": None,
                        "provider_data": {
                            "episode_url": episode_url,
                            "source_type": "html5"
                        }
                    }
                    video_urls.append(video_data)

            # Alternatif: iframe veya embed kaynakları
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                iframe_src = iframe.get('src')
                if iframe_src and ('video' in iframe_src.lower() or 'player' in iframe_src.lower()):
                    video_data = {
                        "url": iframe_src,
                        "quality": "720p",
                        "format": "embed",
                        "size": None,
                        "provider_data": {
                            "episode_url": episode_url,
                            "source_type": "iframe"
                        }
                    }
                    video_urls.append(video_data)

        except Exception as e:
            print(f"Video URL parse hatası: {e}")

        # Kaliteye göre sırala (yüksekten düşüğe)
        quality_order = {'1080p': 4, '720p': 3, '480p': 2, '360p': 1}
        video_urls.sort(key=lambda x: quality_order.get(x['quality'], 0), reverse=True)

        return video_urls

    def _get_video_format(self, url: str) -> str:
        """URL'den video formatını belirle."""
        if '.mp4' in url.lower():
            return 'mp4'
        elif '.m3u8' in url.lower():
            return 'm3u8'
        elif '.webm' in url.lower():
            return 'webm'
        elif '.avi' in url.lower():
            return 'avi'
        elif '.mkv' in url.lower():
            return 'mkv'
        else:
            return 'unknown'


# Kullanım örneği:
if __name__ == "__main__":
    adapter = ExampleAnimeAdapter()

    # Arama testi
    results = adapter.search_anime("attack on titan")
    print(f"Arama sonuçları: {len(results)} anime bulundu")

    if results:
        # İlk sonucu detaylandır
        anime_details = adapter.get_anime_details(results[0]['url'])
        if anime_details:
            print(f"Anime: {anime_details['title']}")

            # Bölümleri al
            episodes = adapter.get_episodes(anime_details)
            print(f"Bölümler: {len(episodes)} bölüm bulundu")

            if episodes:
                # İlk bölümün videolarını al
                videos = adapter.get_video_urls(episodes[0])
                print(f"Video kaynakları: {len(videos)} kaynak bulundu")

                for video in videos:
                    print(f"  - {video['quality']}: {video['url']}")
