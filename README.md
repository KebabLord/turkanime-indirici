
<div align="center">

![TürkAnimu Logo](https://i.imgur.com/GaMNM29.png)

[![GitHub all releases](https://img.shields.io/github/downloads/barkeser2002/turkanime-indirici/total?style=flat-square)](https://github.com/barkeser2002/turkanime-indirici/releases/latest)
[![Downloads](https://static.pepy.tech/personalized-badge/turkanime-gui?period=total&units=international_system&left_color=grey&right_color=orange&left_text=Pip%20Installs)](https://pepy.tech/project/turkanime-gui)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/barkeser2002/turkanime-indirici?style=flat-square)](https://github.com/barkeser2002/turkanime-indirici/releases/latest/download/turkanime-gui-windows.exe)
[![Pypi version](https://img.shields.io/pypi/v/turkanime-gui?style=flat-square)](https://pypi.org/project/turkanime-gui/)

</div>

# TürkAnimu İndirici & Oynatıcı

2019'da basit bir [reverse engineering](https://github.com/barkeser2002/turkanime-indirici/blob/master/turkanime_api/bypass.py) projesi olarak başlamış, nedense hala devam ettirilen terminal tabanlı Türkanime tarayıcısı.

## ✨ Özellikler

- **Yığın ve paralel bölüm indirme**
- **Anime oynatma**, izlerken kaydetme ve kaldığın yerden devam etme
- **Fansub seçimi** ve en yüksek çözünürlükte video bulma
- **Modern GUI arayüzü** ile AniList entegrasyonu
- **AniList ile trend animeler** keşfi ve arama
- **İzleme listesi yönetimi** ve progress senkronizasyonu
- **Netflix tarzı thumbnail katalog** görünümü
- **Discord Rich Presence** entegrasyonu
- **Cross-platform**: Linux, Windows, MacOS, Android

## 🎮 Discord Rich Presence

TürkAnimu GUI, Discord Rich Presence entegrasyonu ile Discord profilinizde şu an ne yaptığınızı arkadaşlarınızla paylaşabilirsiniz:

### Durum Örnekleri:
- **Ana sayfada**: "Ana sayfada" - "TürkAnimu GUI"
- **Trend animelere bakarken**: "Trend animelere bakıyor" - "TürkAnimu GUI"
- **İndirilenlere bakarken**: "İndirilenlere bakıyor" - "TürkAnimu GUI"
- **Anime izlerken**: "{Anime Adı} izliyor" - "Bölüm: {Bölüm Adı}"
- **İndirme sırasında**: "{Anime Adı} indiriyor" - "İlerleme: {Yüzde}%"

### Kurulum:
1. Discord uygulamasının açık olduğundan emin olun
2. Uygulamayı çalıştırın
3. Ayarlar → Discord Rich Presence bölümünden özelliği açıp kapatabilirsiniz
4. Discord profilinizde Rich Presence otomatik olarak görünecektir

**Not:** Bu özellik isteğe bağlıdır. Ayarlardan kapatılabilir ve `pypresence` kütüphanesi yüklü değilse normal çalışmaya devam eder.

## 📺 Ekran Görüntüleri

### İzleme Ekranı
![izleme.gif](https://i.imgur.com/s04Dnox.gif)

### İndirme Ekranı
![indirme.gif](https://i.imgur.com/k7Y3LYA.gif)

## 🎨 GUI ve AniList Özellikleri

- **Birleşik Modern UI**: Keşfet ve AniList sekmeleri tek sayfada birleştirildi
- **OAuth2 AniList Entegrasyonu**: Güvenli giriş sistemi ile AniList hesabınıza bağlanın
- **Çift Taraflı Arama**: Hem yerel kaynaklarda hem AniList'te aynı anda arama yapın
- **Trend Keşfi**: Popüler animeleri görsel katalog halinde keşfedin
- **Akıllı Arama**: AniList veritabanında anime ara
- **İzleme Listesi**: Kişisel listelerinizi yönetin (Current, Planning, Completed, Dropped, Paused)
- **Progress Sync**: İzleme ilerlemenizi AniList ile otomatik senkronize edin
- **Netflix Tarzı UI**: Hover efektleri ve modern card tasarımı
- **Thumbnail Galerisi**: Büyük kapak görselleri ile görsel keşif

## 🔗 Desteklenen Kaynaklar

```
Sibnet  Odnoklassinki  HDVID  Myvi Sendvid  Mail
Amaterasu   Alucard   PixelDrain   VK  MP4upload
Vidmoly   Dailymotion   Yandisk   Uqload   Drive
```

## 📥 Kurulum

### Önceden Derlenmiş Sürümler
En kolay yöntem: [Releases](https://github.com/barkeser2002/turkanime-indirici/releases/latest) sayfasından işletim sisteminize uygun exe dosyasını indirin.

### PyPI ile Kurulum

#### CLI Sürümü (Terminal Arayüzü)
```bash
pip install turkanime-gui
```

#### GUI Sürümü (Grafiksel Arayüz)
```bash
pip install turkanime-gui
```

### Kaynak Koddan Kurulum

#### CLI Sürümü
```bash
git clone https://github.com/barkeser2002/turkanime-indirici.git
cd turkanime-indirici
pip install -r requirements.txt
```

#### GUI Sürümü
```bash
git clone https://github.com/barkeser2002/turkanime-indirici.git
cd turkanime-indirici
pip install -r requirements-gui.txt
```

### 🚀 Çalıştırma

#### CLI Modu
Terminal'de anime indirmek ve oynatmak için:
```bash
# PyPI'den yükledikten sonra
turkanime-cli

# Veya kaynak koddan
python -m turkanime_api.cli
```

#### GUI Modu
Grafiksel arayüz ile kullanmak için:
```bash
# PyPI'den yükledikten sonra
turkanime-gui

# Veya kaynak koddan
python -m turkanime_api.gui.main
```

### 🔧 Sistem Gereksinimleri
- **Python**: 3.9 veya üzeri
- **FFmpeg**: Video işleme için (otomatik indirilir)
- **mpv**: Video oynatma için (GUI için)
- **Git**: Kaynak koddan yükleme için

Daha fazla kurulum detayı için [Wiki](https://github.com/barkeser2002/turkanime-indirici/wiki) sayfasını ziyaret edin.

## 👨‍💻 Geliştirici misin?

Tüm metodları görmek için [dökümantasyona](https://github.com/barkeser2002/turkanime-indirici/wiki) göz atın.

```python
""" Bu API'yı kullanmak bu kadar kolay """
>>> import turkanime_api as ta

# Anime objesini yarat
>>> anime = ta.Anime("non-non-biyori")
>>> print(anime.info)
{'Anime Türü': ['Okul', 'Yaşamdan Kesitler', 'Seinen', 'Komedi'],
 'Başlama Tarihi': '08 Ekim 2013, Salı',
 'Bitiş Tarihi': '24 Aralık 2013, Salı',
 'Bölüm Sayısı': '13 / 12+',
 'Japonca': 'のんのんびより',
 'Kategori': 'TV',
 'Puanı': 8.54,
 'Resim': 'http://www.turkanime.co/imajlar/serilerb/1825.jpg',
 'Stüdyo': 'Silver Link.',
 'Özet': "İlkokula giden Hotaru Ichijou, ailesiyle birlikte Tokyo'dan "
         'memleketine taşınmıştır. Farklı yaşıtlardaki 5 öğrencinin bulunduğu '
         'yeni okuluna uyum sağlamalıdır.'}

>>> bolum4 = anime.bolumler[3]
>>> bolum4.videos[0].url
'https://drive.google.com/file/d/1E8cy53kiuBg13S30M50m_5yS8xnr9aYf/preview'
```

## 🔧 Diğer Türkçe Anime Projeleri

Aşağıdaki projeler de farklı sitelerden anime indirmeyi ve izlemeyi mümkün kılıyor:

- [AniTR-cli](https://github.com/xeyossr/anitr-cli): Go ile yazılmış terminal tabanlı anime oynatıcı
- [AnimeciX-Desktop](https://github.com/CaptainSP/animecix-desktop): AnimeciX üstünden anime indirici ve oynatıcı
- [Turkanime-indiriciGUI](https://github.com/qweeren/turkanime-indirici/tree/master): Tkinter GUI fork'u

## ✅ Yapılacaklar

- [x] Selenium'dan kurtulma
- [x] Maximum çözünürlüğe ulaşma
- [x] Youtube-dl yerine yt-dlp'ye geçiş
- [x] Yeni sürüm kontrolü
- [x] Paralel anime indirme
- [x] Progress sistemi iyileştirme
- [x] Domain güncellemeleri için stabilite
- [x] Kod basitleştirme
- [x] HTTP tabanlı navigasyon
- [x] Sleep'lerden kurtulma
- [x] PyInquirer'den Questionary'e geçiş
- [x] HTTP tabanlı arama
- [x] Fansub seçimi

## 🔒 Doğrulama (MD5 Hash)

### Windows:
```powershell
./docs/hash_dist_md5.bat ./dist/turkanime-gui-windows.exe
```

### Linux/macOS:
```bash
./scripts/hash_md5.sh ./dist/turkanime-gui-linux   # Linux için
./scripts/hash_md5.sh ./dist/turkanime-gui-macos   # macOS için
```

**Not:** CI yayınlarında .md5 dosyaları otomatik olarak eklenir.



