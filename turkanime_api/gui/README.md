Bu klasör, PyQt6 tabanlı TürkAnimu GUI uygulamasını içerir.

## Derleme (lokal)

Önkoşullar:
- Python 3.10–3.12
- Bağımlılıklar (GUI):

```
pip install -r requirements-gui.txt
```

PyInstaller ile tek dosya (spec):

```
python -m PyInstaller pyinstaller.spec
```

Çıktılar `dist/` klasörüne üretilir.

Notlar:
- Proje kökünde `bin/` klasörü varsa içeriği paketlenir (mpv, aria2c, ffmpeg, yt-dlp vb.). CI yalnızca Windows’ta bu klasörü otomatik hazırlar.
- Uygulama simgesi `docs/TurkAnimu.ico` dosyasından yüklenir.

## Çalıştırma

Derlenmiş ikiliyi doğrudan çalıştırın:
- Windows: `dist/turkanime-gui.exe`
- Linux: `dist/turkanime-gui-linux`
- macOS: `dist/turkanime-gui-macos`

Geliştirme modunda çalıştırma:

```
python -m turkanime_api.gui.main
```

Poetry ile:

```
poetry run turkanime-gui
```

macOS ipucu: İndirilen dosya karantinadaysa açılışa izin vermek için Gatekeeper karantinasını kaldırmanız gerekebilir.

## CI / Release

GitHub Actions, tag (vX.Y.Z) atıldığında üç işletim sistemi için derler ve release’e ekler:
- Windows: `turkanime-gui-windows.exe`
- Linux: `turkanime-gui-linux`
- macOS: `turkanime-gui-macos`

Windows derlemelerinde mpv, aria2c, ffmpeg ve yt-dlp, mevcutsa paketlenir. Linux/macOS’ta sistemde bulunmaları önerilir; lokal derlemede `bin/` altına koyarsanız paketlenir.
