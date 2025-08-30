# TürkAnime GUI - Anime Sağlayıcı Ekleme Rehberi

Bu rehber, TürkAnime GUI'ya yeni anime sağlayıcıları nasıl ekleyeceğinizi açıklar.

## Gereksinimler

- Python 3.8+
- BeautifulSoup4
- requests
- py7zr (7z dosyaları için)
- tarfile (Linux/macOS için)

## Adımlar

### 1. Template'i Kopyalayın

```bash
cp turkanime_api/sources/adapter_template.py turkanime_api/sources/my_provider.py
```

### 2. Sağlayıcınızı Düzenleyin

`my_provider.py` dosyasını açın ve aşağıdaki değişiklikleri yapın:

```python
class MyProviderAdapter(TemplateAnimeAdapter):
    """My Provider için adapter."""

    PROVIDER_CONFIG = {
        "name": "My Provider",
        "base_url": "https://myprovider.com",
        "search_url": "https://myprovider.com/search?q={query}",
        "anime_url": "https://myprovider.com/anime/{anime_id}",
        "supported_resolutions": ["360p", "480p", "720p", "1080p"],
        "rate_limit": 2,  # 2 saniye bekleme
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "timeout": 15,
    }
```

### 3. Metodları Implement Edin

#### search_anime(query: str)

Sağlayıcınızda anime arama işlemini gerçekleştirin:

```python
def search_anime(self, query: str) -> List[Dict[str, Any]]:
    search_url = self.PROVIDER_CONFIG['search_url'].format(query=query)
    response = self._make_request(search_url)

    if not response:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    results = []

    # Sağlayıcınızın HTML yapısına göre parse edin
    for item in soup.find_all('div', class_='anime-item'):
        title_elem = item.find('h3', class_='anime-title')
        url_elem = item.find('a', class_='anime-link')
        image_elem = item.find('img', class_='anime-image')

        if title_elem and url_elem:
            results.append({
                "title": title_elem.text.strip(),
                "url": url_elem['href'],
                "image": image_elem['src'] if image_elem else None,
                "provider_data": {
                    "item_id": item.get('data-id'),
                    "search_query": query
                }
            })

    return results
```

#### get_anime_details(anime_url: str)

Anime detaylarını getirin:

```python
def get_anime_details(self, anime_url: str) -> Optional[Dict[str, Any]]:
    response = self._make_request(anime_url)

    if not response:
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    return {
        "title": soup.find('h1', class_='anime-title').text.strip(),
        "description": soup.find('div', class_='anime-description').text.strip(),
        "image": soup.find('img', class_='anime-poster')['src'],
        "genres": [g.text for g in soup.find_all('span', class_='genre')],
        "year": int(soup.find('span', class_='year').text),
        "episodes": int(soup.find('span', class_='episodes').text),
        "status": soup.find('span', class_='status').text,
        "score": float(soup.find('span', class_='score').text),
        "provider_data": {"anime_url": anime_url}
    }
```

#### get_episodes(anime_data: Dict[str, Any])

Anime bölümlerini listeleyin:

```python
def get_episodes(self, anime_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    anime_url = anime_data['provider_data']['anime_url']
    response = self._make_request(anime_url)

    if not response:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    episodes = []

    for item in soup.find_all('div', class_='episode-item'):
        episodes.append({
            "title": item.find('h4', class_='episode-title').text.strip(),
            "episode_number": int(item.find('span', class_='episode-number').text),
            "url": item.find('a', class_='episode-link')['href'],
            "thumbnail": item.find('img', class_='episode-thumb')['src'],
            "provider_data": {"episode_id": item.get('data-id')}
        })

    return episodes
```

#### get_video_urls(episode_data: Dict[str, Any])

Video kaynaklarını getirin:

```python
def get_video_urls(self, episode_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    episode_url = episode_data['url']
    response = self._make_request(episode_url)

    if not response:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    video_urls = []

    # HTML5 video kaynakları
    for source in soup.find_all('source'):
        video_urls.append({
            "url": source['src'],
            "quality": source.get('data-quality', '720p'),
            "format": "mp4",
            "provider_data": {"source_type": "html5"}
        })

    # iframe/embed kaynakları
    for iframe in soup.find_all('iframe'):
        if 'video' in iframe.get('src', '').lower():
            video_urls.append({
                "url": iframe['src'],
                "quality": "720p",
                "format": "embed",
                "provider_data": {"source_type": "iframe"}
            })

    return video_urls
```

### 4. Sağlayıcıyı Kaydedin

`turkanime_api/sources/__init__.py` dosyasına import ekleyin:

```python
from .my_provider import MyProviderAdapter  # noqa: F401
```

Ve PROVIDERS sözlüğüne ekleyin:

```python
PROVIDERS = {
    "animecix": {
        "name": "AnimeciX",
        "adapter": None,  # Eski sistem
        "enabled": True,
        "priority": 1
    },
    "my_provider": {
        "name": "My Provider",
        "adapter": MyProviderAdapter,
        "enabled": True,
        "priority": 2
    }
}
```

### 5. Test Edin

Sağlayıcınızı test etmek için basit bir test yazın:

```python
if __name__ == "__main__":
    adapter = MyProviderAdapter()

    # Arama testi
    results = adapter.search_anime("attack on titan")
    print(f"Bulunan sonuçlar: {len(results)}")

    if results:
        # Detay testi
        details = adapter.get_anime_details(results[0]['url'])
        print(f"Anime: {details['title']}")

        # Bölüm testi
        episodes = adapter.get_episodes(details)
        print(f"Bölümler: {len(episodes)}")

        if episodes:
            # Video testi
            videos = adapter.get_video_urls(episodes[0])
            print(f"Video kaynakları: {len(videos)}")
```

## İpuçları

1. **Rate Limiting**: Sağlayıcınızın rate limit'lerine uyun
2. **Error Handling**: Ağ hatalarını graceful bir şekilde handle edin
3. **User Agent**: Gerçekçi user agent kullanın
4. **Timeouts**: Uygun timeout değerleri belirleyin
5. **HTML Parsing**: Sağlayıcının HTML yapısını iyi analiz edin
6. **Video Formats**: Farklı video formatlarını destekleyin (mp4, m3u8, vb.)
7. **Caching**: Sık kullanılan verileri cache'leyin

## Örnek Sağlayıcılar

- [AnimeciX](https://animecix.net) - Mevcut implementasyon
- [TürkAnime](https://turkanime.tv) - Orijinal sağlayıcı

## Destek

Sorularınız için GitHub Issues kullanın
