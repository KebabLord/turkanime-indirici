from __future__ import annotations

from typing import List, Dict, Optional
import sys
import os
import concurrent.futures as cf
import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk
from PIL import Image
import threading
import webbrowser
import requests
import io
import json
import time
import appdirs
import tempfile
import platform
from zipfile import ZipFile
from py7zr import SevenZipFile
import tarfile
from shutil import move

from turkanime_api.objects import Anime, Bolum
from turkanime_api.bypass import fetch
from turkanime_api.cli.dosyalar import Dosyalar
from turkanime_api.cli.cli_tools import VidSearchCLI, indir_aria2c
from turkanime_api.cli.gereksinimler import Gereksinimler
from turkanime_api.sources.animecix import CixAnime, search_animecix
from turkanime_api.sources.adapter import AdapterAnime, AdapterBolum
from turkanime_api.anilist_client import anilist_client, AniListAuthServer
from turkanime_api.gui.update_manager import UpdateManager
from turkanime_api.common.utils import get_platform, get_arch
from turkanime_api.common.ui_helpers import create_progress_section

try:
    from pypresence import Presence
    DISCORD_RPC_AVAILABLE = True
except ImportError:
    DISCORD_RPC_AVAILABLE = False


class RequirementsManager:
    """GUI için gereksinimler yönetim sistemi."""

    def __init__(self, parent_window):
        self.parent = parent_window
        self.dosyalar = Dosyalar()
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.requirements_url = "https://raw.githubusercontent.com/KebabLord/turkanime-indirici/master/gereksinimler.json"
        self.platform = get_platform()
        self.arch = get_arch()
        if self.platform == 'windows':
            self.required_deps = ["yt-dlp", "mpv", "aria2c", "ffmpeg"]
        else:
            self.required_deps = []

    def _get_embedded_tool_path(self, tool_name):
        """Embed edilmiş aracın yolunu döndür."""
        try:
            # PyInstaller ile gömülü ise
            base_path = getattr(sys, "_MEIPASS", None)
            if base_path:
                tool_path = os.path.join(base_path, "bin", tool_name)
                if os.path.exists(tool_path):
                    return tool_path
            
            # Geliştirme ortamında
            tool_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "bin", tool_name)
            if os.path.exists(tool_path):
                return tool_path
            
            return None
        except:
            return None

    def check_requirements(self):
        """Gereksinimleri kontrol et ve eksik olanları döndür."""
        missing = []
        for dep in self.required_deps:
            if not self._is_app_available(dep):
                missing.append(dep)
        return missing

    def _is_app_available(self, app_name):
        """Uygulamanın mevcut olup olmadığını kontrol et."""
        try:
            import subprocess
            # Özel kontrol: mpv için placeholder kontrolü
            if app_name == "mpv":
                mpv_path = self._get_embedded_tool_path("mpv.exe")
                if mpv_path and os.path.exists(mpv_path):
                    # Placeholder kontrolü
                    with open(mpv_path, 'r', encoding='utf-8', errors='ignore') as f:
                        first_line = f.readline().strip()
                        if first_line.startswith("#"):
                            return False  # Placeholder, gerçek mpv yok
                else:
                    return False
            
            result = subprocess.run([app_name, "--version"],
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False

    def download_requirements(self, missing_deps, progress_callback=None):
        """Eksik gereksinimleri indir ve kur."""
        try:
            # Gereksinimler listesini al
            response = requests.get(self.requirements_url, timeout=10)
            response.raise_for_status()
            requirements = response.json()

            results = []
            for dep in missing_deps:
                if progress_callback:
                    progress_callback(f"{dep} indiriliyor...")

                # Bu gereksinim için uygun URL'yi bul
                req_data = None
                for req in requirements:
                    if req["name"] == dep:
                        req_data = req
                        break

                if not req_data:
                    results.append({"name": dep, "success": False, "error": "Gereksinim bulunamadı"})
                    continue

                # Platform ve mimariye göre URL seç
                platforms = req_data.get("platforms", {})
                platform_data = platforms.get(self.platform, {})
                url = platform_data.get(self.arch, platform_data.get("x64", ""))

                if not url:
                    results.append({"name": dep, "success": False, "error": "Platform desteklenmiyor"})
                    continue

                # Dosyayı indir
                success, error = self._download_and_install(url, req_data, progress_callback)
                results.append({"name": dep, "success": success, "error": error})

            return results

        except Exception as e:
            return [{"name": "Genel", "success": False, "error": str(e)}]

    def _download_and_install(self, url, req_data, progress_callback):
        """Dosyayı indir ve kur."""
        try:
            if progress_callback:
                progress_callback(f"Dosya indiriliyor: {url.split('/')[-1]}")

            # Özel durum: mpv placeholder ise gerçek mpv'yi indir
            if req_data["name"] == "mpv":
                mpv_path = self._get_embedded_tool_path("mpv.exe")
                if mpv_path and os.path.exists(mpv_path):
                    with open(mpv_path, 'r', encoding='utf-8', errors='ignore') as f:
                        first_line = f.readline().strip()
                        if first_line.startswith("#"):
                            # Placeholder, gerçek mpv'yi indir
                            return self._download_real_mpv(url, req_data, progress_callback)

            # Normal indirme işlemi
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            filename = url.split("/")[-1]
            filepath = os.path.join(self.tmp_dir.name, filename)

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            # Dosyayı kur
            return self._install_file(filepath, req_data, progress_callback)

        except Exception as e:
            return False, str(e)

    def _download_real_mpv(self, url, req_data, progress_callback):
        """mpv için gerçek indirme işlemi (placeholder yerine)."""
        try:
            if progress_callback:
                progress_callback("Gerçek mpv indiriliyor...")

            # mpv için daha güvenilir bir kaynak kullan
            if self.platform == "windows":
                # Windows için portable mpv indir
                mpv_url = "https://github.com/shinchiro/mpv-winbuild-cmake/releases/download/20231231/mpv-x86_64-20231231-git-abc2a74.7z"
                filename = "mpv.7z"
            else:
                # Diğer platformlar için normal URL kullan
                mpv_url = url
                filename = url.split("/")[-1]

            response = requests.get(mpv_url, stream=True, timeout=30)
            response.raise_for_status()

            filepath = os.path.join(self.tmp_dir.name, filename)

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            # mpv'yi özel olarak kur
            return self._install_mpv_file(filepath, req_data, progress_callback)

        except Exception as e:
            return False, str(e)

    def _install_mpv_file(self, filepath, req_data, progress_callback):
        """mpv dosyasını özel olarak kur."""
        try:
            if progress_callback:
                progress_callback("mpv kuruluyor...")

            filename = os.path.basename(filepath)
            file_ext = filename.split(".")[-1].lower()

            if self.platform == "windows":
                # Windows için 7z çıkarma
                if file_ext == "7z":
                    import subprocess
                    # 7z ile çıkar
                    result = subprocess.run([
                        "C:\\Program Files\\7-Zip\\7z.exe", "x", filepath, 
                        f"-o{self.tmp_dir.name}\\mpv_extracted", "-y"
                    ], capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        # mpv.exe'yi bul ve bin klasörüne kopyala
                        extracted_dir = os.path.join(self.tmp_dir.name, "mpv_extracted")
                        for root, dirs, files in os.walk(extracted_dir):
                            for file in files:
                                if file.lower() == "mpv.exe":
                                    src_path = os.path.join(root, file)
                                    dest_path = self._get_embedded_tool_path("mpv.exe")
                                    if dest_path:
                                        import shutil
                                        shutil.copy2(src_path, dest_path)
                                        return True, None
                        
                        return False, "mpv.exe extracted folder'da bulunamadı"
                    else:
                        return False, f"7z extraction failed: {result.stderr}"
                else:
                    return False, f"Unsupported file type for mpv: {file_ext}"
            else:
                # Diğer platformlar için normal kurulum
                return self._install_file(filepath, req_data, progress_callback)

        except Exception as e:
            return False, str(e)

    def _install_file(self, filepath, req_data, progress_callback):
        """İndirilen dosyayı kur."""
        try:
            filename = os.path.basename(filepath)
            file_ext = filename.split(".")[-1].lower()

            if progress_callback:
                progress_callback(f"Dosya kuruluyor: {filename}")

            # Geçici dizin oluştur
            extract_dir = tempfile.mkdtemp()

            # Dosyayı çıkar
            if file_ext == "7z":
                with SevenZipFile(filepath, mode='r') as archive:
                    archive.extractall(extract_dir)
            elif file_ext == "zip":
                with ZipFile(filepath, 'r') as archive:
                    archive.extractall(extract_dir)
            elif file_ext in ["xz", "gz", "bz2"]:
                with tarfile.open(filepath, 'r:*') as archive:
                    archive.extractall(extract_dir)
            elif file_ext == "exe":
                if req_data.get("is_setup", False):
                    # Setup dosyası - çalıştır
                    os.system(f'"{filepath}"')
                    return True, None
                else:
                    # Direkt kopyala
                    dest_path = os.path.join(self.dosyalar.ta_path, filename)
                    move(filepath, dest_path)
                    return True, None
            else:
                return False, f"Desteklenmeyen dosya türü: {file_ext}"

            # Uygulama dosyasını bul ve taşı
            app_files = []
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    if req_data["name"] in file.lower() or file.lower().startswith(req_data["name"]):
                        app_files.append(os.path.join(root, file))

            if not app_files:
                # İlk executable dosyayı kullan
                for root, dirs, files in os.walk(extract_dir):
                    for file in files:
                        if file_ext in ["exe", ""] or not "." in file:
                            app_files.append(os.path.join(root, file))
                            break
                    if app_files:
                        break

            if app_files:
                dest_path = os.path.join(self.dosyalar.ta_path, os.path.basename(app_files[0]))
                move(app_files[0], dest_path)
                return True, None
            else:
                return False, "Uygulama dosyası bulunamadı"

        except Exception as e:
            return False, str(e)


class WorkerSignals:
    """CustomTkinter için sinyal benzeri sınıf."""

    def __init__(self):
        self.progress_callbacks = []
        self.progress_item_callbacks = []
        self.error_callbacks = []
        self.error_item_callbacks = []
        self.success_callbacks = []
        self.found_callbacks = []

    def connect_progress(self, callback):
        self.progress_callbacks.append(callback)

    def connect_progress_item(self, callback):
        self.progress_item_callbacks.append(callback)

    def connect_error(self, callback):
        self.error_callbacks.append(callback)

    def connect_error_item(self, callback):
        self.error_item_callbacks.append(callback)

    def connect_success(self, callback):
        self.success_callbacks.append(callback)

    def connect_found(self, callback):
        self.found_callbacks.append(callback)

    def emit_progress(self, msg):
        for cb in self.progress_callbacks:
            cb(msg)

    def emit_progress_item(self, data):
        for cb in self.progress_item_callbacks:
            cb(data)

    def emit_error(self, msg):
        for cb in self.error_callbacks:
            cb(msg)

    def emit_error_item(self, data):
        for cb in self.error_item_callbacks:
            cb(data)

    def emit_success(self):
        for cb in self.success_callbacks:
            cb()

    def emit_found(self, data):
        for cb in self.found_callbacks:
            cb(data)


class DownloadWorker:
    """CustomTkinter için indirme worker'ı."""

    def __init__(self, bolumler: List[Bolum], update_callback=None):
        self.bolumler = bolumler
        self.signals = WorkerSignals()
        self.update_callback = update_callback

    def run(self):
        try:
            dosya = Dosyalar()
            paralel = dosya.ayarlar.get("paralel indirme sayisi", 2)

            def dl_one(bolum: Bolum):
                self.signals.emit_progress(f"{bolum.slug} için video aranıyor…")
                self.signals.emit_progress_item({
                    "slug": bolum.slug,
                    "title": bolum.title,
                    "status": "hazır",
                    "downloaded": 0,
                    "total": None,
                    "percent": 0,
                    "speed": None,
                    "eta": None,
                })
                best_video = bolum.best_video(
                    by_res=dosya.ayarlar.get("max resolution", True),
                    early_subset=dosya.ayarlar.get("1080p aday sayısı", 8),
                )
                if not best_video:
                    self.signals.emit_error_item({
                        "slug": bolum.slug,
                        "title": bolum.title,
                        "error": "Uygun video bulunamadı",
                    })
                    return
                down_dir = dosya.ayarlar.get("indirilenler", ".")

                last = {"t": None, "b": 0}
                def hook(h):
                    # İlerleme bilgilerini topla
                    st = h.get("status")
                    # aria2c hata mesajı varsa GUI loguna da düş
                    if st == "error":
                        msg = h.get("message")
                        if msg:
                            self.signals.emit_progress(f"{bolum.slug}: aria2c hata: {msg}")
                    cur = h.get("downloaded_bytes") or h.get("downloaded")
                    tot = h.get("total_bytes") or h.get("total_bytes_estimate") or h.get("total")
                    eta = h.get("eta")
                    spd = h.get("speed")
                    # Hız yoksa hesaplamayı dene
                    try:
                        import time
                        now = time.time()
                        if cur is not None:
                            if last["t"] is not None:
                                dt = max(1e-3, now - last["t"])
                                db = max(0, cur - last["b"]) if last["b"] is not None else 0
                                if db > 0:
                                    spd = db / dt
                            last["t"], last["b"] = now, cur
                    except Exception:
                        pass

                    # Yüzde
                    pct = None
                    if cur and tot:
                        try:
                            pct = int(cur * 100 / tot)
                        except Exception:
                            pct = None

                    # Genel durum mesajı
                    if st == "downloading":
                        if cur and tot:
                            self.signals.emit_progress(f"{bolum.slug}: {int(cur/1024/1024)}/{int(tot/1024/1024)} MB")
                        else:
                            self.signals.emit_progress(f"{bolum.slug}: indiriliyor…")
                    elif st == "finished":
                        self.signals.emit_progress(f"{bolum.slug}: indirildi")

                    # Tablo güncellemesi
                    self.signals.emit_progress_item({
                        "slug": bolum.slug,
                        "title": bolum.title,
                        "status": ("indiriliyor" if st == "downloading" else "indirildi" if st == "finished" else st),
                        "downloaded": cur,
                        "total": tot,
                        "percent": pct,
                        "speed": spd,
                        "eta": eta,
                    })

                success = False
                if best_video.player != "ALUCARD(BETA)" and dosya.ayarlar.get("aria2c kullan"):
                    try:
                        success = bool(indir_aria2c(best_video, callback=hook, output=down_dir))
                    except Exception:
                        # Güvenli geri dönüş: yt-dlp ile devam et
                        try:
                            best_video.indir(callback=hook, output=down_dir)
                            success = True
                        except Exception:
                            success = False
                else:
                    try:
                        best_video.indir(callback=hook, output=down_dir)
                        success = True
                    except Exception:
                        if success:
                            dosya.set_gecmis(bolum.anime.slug if bolum.anime else "", bolum.slug, "indirildi")
                            # İndirilenler listesini güncelle
                            if self.update_callback:
                                self.update_callback(bolum, down_dir)
                            # Tamamlandı sinyali
                        self.signals.emit_progress_item({
                            "slug": bolum.slug,
                            "title": bolum.title,
                            "status": ("tamamlandı" if success else "hata"),
                            "downloaded": last.get("b"),
                            "total": last.get("b"),
                            "percent": (100 if success else None),
                            "speed": None,
                            "eta": 0,
                        })

            with cf.ThreadPoolExecutor(max_workers=paralel) as executor:
                futures = [executor.submit(dl_one, b) for b in self.bolumler]
                for fut in cf.as_completed(futures):
                    fut.result()
            self.signals.emit_success()
        except Exception as e:
            self.signals.emit_error(str(e))


class VideoFindWorker:
    """Bölüm için en uygun videoyu bulur ve sonucu döndürür."""

    def __init__(self, bolum: Bolum):
        self.bolum = bolum
        self.signals = WorkerSignals()

    def run(self):
        try:
            dosya = Dosyalar()
            vid_cli = VidSearchCLI()
            best = self.bolum.best_video(
                by_res=dosya.ayarlar.get("max resolution", True),
                early_subset=dosya.ayarlar.get("1080p aday sayısı", 8),
                callback=vid_cli.callback,
            )
            if not best:
                self.signals.emit_error("Uygun video bulunamadı")
                return
            self.signals.emit_progress("Video bulundu")
            self.signals.emit_success()
            self.signals.emit_found(best)
        except Exception as e:
            self.signals.emit_error(str(e))


class SearchWorker:
    """Kaynağa göre arama yapan worker."""

    def __init__(self, source: str, query: str):
        self.source = source
        self.query = query
        self.signals = WorkerSignals()

    def run(self):
        try:
            results = []
            q = (self.query or "").strip()
            if not q:
                self.signals.emit_found([])
                return
            if self.source == "TürkAnime":
                all_list = Anime.get_anime_listesi()
                for slug, name in all_list:
                    if q.lower() in (name or "").lower():
                        results.append({"source": "TürkAnime", "slug": slug, "title": name})
            else:
                for _id, name in search_animecix(q):
                    results.append({"source": "AnimeciX", "id": int(_id), "title": name})
            self.signals.emit_found(results)
        except Exception as e:
            self.signals.emit_error(str(e))


class EpisodesWorker:
    """Seçilen anime için bölüm listesini yükler."""

    def __init__(self, anime_item: dict):
        self.anime_item = anime_item
        self.signals = WorkerSignals()

    def run(self):
        try:
            src = self.anime_item.get("source")
            out_items = []
            if src == "TürkAnime":
                ani = Anime(self.anime_item.get("slug"))
                bolumler = ani.bolumler
                for b in bolumler:
                    out_items.append({"title": b.title, "obj": b})
            else:
                anime_id = self.anime_item.get("id")
                anime_title = self.anime_item.get("title")
                if anime_id and anime_title:
                    cix = CixAnime(id=int(anime_id), title=anime_title)
                    cix_eps = cix.episodes
                    ada = AdapterAnime(slug=str(cix.id), title=cix.title)
                    for e in cix_eps:
                        ab = AdapterBolum(url=e.url, title=e.title, anime=ada)
                        out_items.append({"title": e.title, "obj": ab})
            self.signals.emit_found(out_items)
        except Exception as e:
            self.signals.emit_error(str(e))


def _resource_path(rel_path: str) -> str:
    """PyInstaller tek-dosya ve geliştirme ortamında kaynak yolu çözer.

    - Çalışma zamanı (_MEIPASS) içinde: docs klasörü Analysis.datas ile köke kopyalanır.
      boot.py ve spec, docs/TurkAnimu.ico'yu datas'a ekliyor; bu yüzden _MEIPASS/docs/... bekleriz.
    - Geliştirme sırasında: proje kökü altındaki göreli yol kullanılır.
    """
    try:
        base = getattr(sys, "_MEIPASS", None)
        if base and os.path.isdir(base):
            cand = os.path.join(base, rel_path)
            if os.path.exists(cand):
                return cand
    except Exception:
        pass
    # Proje kökü: bu dosyanın 3 üstü
    try:
        root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        cand = os.path.join(root, rel_path)
        if os.path.exists(cand):
            return cand
    except Exception:
        pass
    # Son çare: göreli yol
    return rel_path


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("TürkAnimu Gui by @barkeser2002") # Kalsın
        self.geometry("1400x900")

        # App icon (Windows: .ico, Others: .png via iconphoto)
        try:
            ico_path = _resource_path(os.path.join('docs', 'TurkAnimu.ico'))
            if os.path.exists(ico_path):
                # On Windows, iconbitmap expects .ico and updates taskbar/title icon
                self.iconbitmap(ico_path)
            else:
                png_path = _resource_path(os.path.join('docs', 'TurkAnimu.png'))
                if os.path.exists(png_path):
                    self._app_icon_ref = tk.PhotoImage(file=png_path)
                    self.iconphoto(True, self._app_icon_ref)
        except Exception:
            pass

        self.dosya = Dosyalar()

        # Değişkenler
        self.anilist_auth_server = None
        self.anilist_user = None
        self.anilist_current_list_type = "CURRENT"  # CURRENT, PLANNING, COMPLETED, DROPPED, PAUSED
        self.anilist_trending_cache = []
        self.anilist_search_cache = {}
        self.anilist_image_cache = {}
        self.local_anime_progress = {}
        self.current_view = "home"  # home, search, trending, watchlist
        self.selected_anime = None  # Seçili anime için
        self.selected_source = "AnimeciX"  # Varsayılan kaynak
        self.downloaded_episodes = []  # İndirilen bölümler listesi

        # Discord Rich Presence değişkenleri
        self.discord_rpc = None
        self.discord_connected = False
        self.discord_update_timer = None

        # Ana container
        self.main_container = ctk.CTkFrame(self, fg_color="#0f0f0f")
        self.main_container.pack(fill="both", expand=True)

        # Header/Navigation
        self.create_header()

        # Ana içerik alanı
        self.content_area = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        self.content_area.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Ana sayfa içeriği
        self.create_home_content()

        # Alt bar
        self.create_bottom_bar()

        # Gereksinimler kontrolü
        self.requirements_manager = RequirementsManager(self)
        self.update_manager = UpdateManager(self, current_version="1.0.0")
        self.check_requirements_on_startup()

        # Discord Rich Presence'i başlat
        self.init_discord_rpc()

    def init_discord_rpc(self):
        """Discord Rich Presence'i başlat."""
        # Ayarlardan Discord Rich Presence'in açık olup olmadığını kontrol et
        dosya = Dosyalar()
        if not dosya.ayarlar.get("discord_rich_presence", True):
            self.discord_connected = False
            return

        try:
            self.discord_rpc = Presence("1115609536552771595")  # Application ID
            self.discord_rpc.connect()
            self.discord_connected = True
            
            # Başlangıç durumu
            self.update_discord_presence("Ana sayfada", "TürkAnimu GUI")
            
            # Periyodik güncelleme için timer başlat
            self.discord_update_timer = self.after(15000, self.update_discord_presence_periodic)
            
            # Buton rengini güncelle
            self.update_discord_button_color()
            
        except Exception as e:
            print(f"Discord RPC bağlantı hatası: {e}")
            self.discord_connected = False
            self.discord_rpc = None

    def update_discord_presence(self, details, state, large_image="turkanimu", small_image=None, 
                               large_text="TürkAnimu", small_text=None, start_time=None, buttons=None):
        """Discord Rich Presence'i güncelle."""
        if not self.discord_connected or not self.discord_rpc:
            return
            
        try:
            presence_data = {
                "details": details,
                "state": state,
                "large_image": large_image,
                "large_text": large_text
            }
            
            if small_image:
                presence_data["small_image"] = small_image
            if small_text:
                presence_data["small_text"] = small_text
            if start_time:
                presence_data["start"] = start_time
                
            # Button desteği ekle
            if buttons:
                presence_data["buttons"] = buttons
            else:
                # Varsayılan button - uygulamayı edin
                presence_data["buttons"] = [
                    {
                        "label": "Uygulamayı Edin",
                        "url": "https://github.com/barkeser2002/turkanime-indirici/releases"
                    }
                ]
                
            self.discord_rpc.update(**presence_data)
            
        except Exception as e:
            print(f"Discord RPC güncelleme hatası: {e}")
            # Bağlantı kaybı durumunda yeniden bağlanmayı dene
            self.discord_connected = False
            self.attempt_reconnect_discord()

    def update_discord_presence_periodic(self):
        """Periyodik Discord Rich Presence güncellemesi."""
        if not self.discord_connected:
            return

        try:
            # Mevcut view'a göre durumu güncelle
            if hasattr(self, 'current_view'):
                if self.current_view == "home":
                    self.update_discord_presence("Ana sayfada", "TürkAnimu GUI")
                elif self.current_view == "trending":
                    self.update_discord_presence("Trend animelere bakıyor", "TürkAnimu GUI")
                elif self.current_view == "downloads":
                    self.update_discord_presence("İndirilenlere bakıyor", "TürkAnimu GUI")
                elif self.current_view == "watchlist":
                    self.update_discord_presence("İzleme listesine bakıyor", "TürkAnimu GUI")
                else:
                    self.update_discord_presence("Anime arıyor", "TürkAnimu GUI")

            # 15 saniye sonra tekrar güncelle
            self.discord_update_timer = self.after(15000, self.update_discord_presence_periodic)

        except Exception as e:
            print(f"Discord RPC periyodik güncelleme hatası: {e}")
            self.discord_connected = False
            self.attempt_reconnect_discord()

    def update_discord_presence_anime(self, anime_title, episode_info=None, anime_image=None, buttons=None):
        """Anime izlerken Discord Rich Presence'i güncelle."""
        if not self.discord_connected:
            return

        try:
            details = f"{anime_title} izliyor"
            state = episode_info if episode_info else "Anime izliyor"

            # Anime resmi varsa kullan, yoksa default
            large_image = "turkanimu"  # default
            large_text = anime_title

            # Anime resmi varsa kullan (URL'yi Discord'a uygun formata çevir)
            if anime_image:
                # Discord Rich Presence için resmi base64'e çevir veya URL kullan
                try:
                    # Basit URL kontrolü
                    if anime_image.startswith('http'):
                        # Discord Rich Presence için resmi küçültülmüş versiyonunu kullan
                        # AniList'in large resmi çok büyük olabilir, medium kullan
                        if 'large' in anime_image:
                            anime_image = anime_image.replace('large', 'medium')
                        large_image = anime_image
                        large_text = f"{anime_title} - {episode_info}" if episode_info else anime_title
                except:
                    pass

            # Başlangıç zamanını ekle
            import time
            start_time = time.time()

            self.update_discord_presence(details, state, large_image=large_image,
                                       large_text=large_text, start_time=start_time, buttons=buttons)

        except Exception as e:
            print(f"Discord RPC anime güncelleme hatası: {e}")
            # Hata durumunda basit güncelleme dene
            try:
                self.update_discord_presence(f"{anime_title} izliyor",
                                           episode_info if episode_info else "Anime izliyor")
            except Exception:
                pass

    def attempt_reconnect_discord(self):
        """Discord Rich Presence bağlantısını yeniden kurmayı dene."""
        if not DISCORD_RPC_AVAILABLE:
            return

        # Ayarlardan Discord Rich Presence'in açık olup olmadığını kontrol et
        dosya = Dosyalar()
        if not dosya.ayarlar.get("discord_rich_presence", True):
            return

        try:
            print("Discord RPC yeniden bağlanmaya çalışılıyor...")
            self.discord_rpc = Presence("1115609536552771595")
            self.discord_rpc.connect()
            self.discord_connected = True
            print("Discord RPC yeniden bağlandı")

            # Mevcut durumu güncelle
            self.update_discord_presence("TürkAnimu'ya geri döndü", "TürkAnimu GUI")

            # Periyodik güncellemeyi yeniden başlat
            if hasattr(self, 'discord_update_timer') and self.discord_update_timer:
                self.after_cancel(self.discord_update_timer)
            self.discord_update_timer = self.after(15000, self.update_discord_presence_periodic)
            
            # Buton rengini güncelle
            self.update_discord_button_color()

        except Exception as e:
            print(f"Discord RPC yeniden bağlanma hatası: {e}")
            self.discord_connected = False
            # 30 saniye sonra tekrar dene
            self.after(30000, self.attempt_reconnect_discord)

    def disconnect_discord_rpc(self):
        """Discord Rich Presence bağlantısını kapat."""
        try:
            if self.discord_rpc:
                self.discord_rpc.clear()
                self.discord_rpc.close()
                self.discord_rpc = None
            self.discord_connected = False

            # Timer'ı iptal et
            if hasattr(self, 'discord_update_timer') and self.discord_update_timer:
                self.after_cancel(self.discord_update_timer)
                
        except Exception as e:
            print(f"Discord RPC kapatma hatası: {e}")
            
        # Buton rengini güncelle
        self.update_discord_button_color()

    def update_discord_button_color(self):
        """Discord butonunun rengini bağlantı durumuna göre güncelle."""
        # Discord test butonu kaldırıldı, bu fonksiyon artık kullanılmıyor
        pass

    def update_discord_presence_download(self, anime_title, progress=None):
        """İndirme sırasında Discord Rich Presence'i güncelle."""
        if not self.discord_connected:
            return
            
        try:
            details = f"{anime_title} indiriyor"
            state = f"İlerleme: {progress}%" if progress else "Anime indiriyor"
            self.update_discord_presence(details, state)
            
        except Exception as e:
            print(f"Discord RPC indirme güncelleme hatası: {e}")

    def create_header(self):
        """Modern header oluştur."""
        header_frame = ctk.CTkFrame(self.main_container, fg_color="#1a1a1a", height=70)
        header_frame.pack(fill="x", padx=0, pady=0)
        header_frame.pack_propagate(False)

        # Logo ve başlık
        logo_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        logo_frame.pack(side="left", padx=8, pady=8)

        # Logo ikonu
        try:
            icon_path = _resource_path(os.path.join('docs', 'TurkAnimu.png'))
            if os.path.exists(icon_path):
                logo_image = ctk.CTkImage(Image.open(icon_path), size=(28, 28))
                logo_label = ctk.CTkLabel(logo_frame, image=logo_image, text="")
                logo_label.pack(side="left", padx=(0, 8))
        except Exception:
            pass

        # Başlık
        title_label = ctk.CTkLabel(logo_frame, text="TürkAnimu",
                                 font=ctk.CTkFont(size=20, weight="bold"),
                                 text_color="#ff6b6b")
        title_label.pack(side="left")

        subtitle = ctk.CTkLabel(logo_frame, text="Anime Keşif Platformu",
                              font=ctk.CTkFont(size=8),
                              text_color="#888888")
        subtitle.pack(side="left", padx=(6, 0))

        # Ana navigasyon
        nav_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        nav_frame.pack(side="left", padx=8)

        self.btnHome = ctk.CTkButton(nav_frame, text="Ana Sayfa", command=self.show_home,
                                   fg_color="transparent", text_color="#ffffff",
                                   font=ctk.CTkFont(size=9, weight="bold"))
        self.btnHome.pack(side="left", padx=1)

        self.btnTrending = ctk.CTkButton(nav_frame, text="Trend", command=self.show_trending,
                                       fg_color="transparent", text_color="#cccccc",
                                       font=ctk.CTkFont(size=9))
        self.btnTrending.pack(side="left", padx=1)

        self.btnDownloads = ctk.CTkButton(nav_frame, text="İndirilenler", command=self.show_downloads,
                                        fg_color="transparent", text_color="#cccccc",
                                        font=ctk.CTkFont(size=9))
        self.btnDownloads.pack(side="left", padx=1)

        # Listem butonu - sadece giriş yapıldıysa göster
        self.btnWatchlist = ctk.CTkButton(nav_frame, text="Listem", command=self.show_watchlist,
                                        fg_color="transparent", text_color="#cccccc",
                                        font=ctk.CTkFont(size=9))
        # Başlangıçta gizli, check_anilist_auth_status'te kontrol edilecek

        # Arama çubuğu
        search_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        search_frame.pack(side="left", padx=6, expand=True)

        # Kaynak seçimi
        source_frame = ctk.CTkFrame(search_frame, fg_color="transparent")
        source_frame.pack(side="left", padx=(0, 8))

        source_label = ctk.CTkLabel(source_frame, text="Kaynak:",
                                  font=ctk.CTkFont(size=9, weight="bold"))
        source_label.pack(side="left", padx=(0, 5))

        self.cmbSource = ctk.CTkComboBox(source_frame, values=["TürkAnime", "AnimeciX"],
                                       width=100, height=32,
                                       command=self.on_source_change)
        self.cmbSource.pack(side="left")

        self.searchEntry = ctk.CTkEntry(search_frame, placeholder_text="Anime ara...",
                                      width=120, height=32,
                                      font=ctk.CTkFont(size=11))
        self.searchEntry.pack(side="left", padx=(0, 2))

        self.btnSearch = ctk.CTkButton(search_frame, text="🔍", width=40, height=32,
                                     command=self.on_search)
        self.btnSearch.pack(side="left")

        # Sağ taraf - Kullanıcı alanı
        user_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        user_frame.pack(side="right", padx=6)

        # AniList göster/gizle butonu
        self.btnAniListToggle = ctk.CTkButton(user_frame, text="👤 Göster",
                                            command=self.toggle_anilist_panel,
                                            fg_color="#4ecdc4", hover_color="#45b7aa",
                                            width=65, height=32)
        self.btnAniListToggle.pack(side="left", padx=(0, 1))

        # AniList butonları (varsayılan olarak gizli)
        self.anilist_panel = ctk.CTkFrame(user_frame, fg_color="transparent")
        self.anilist_panel.pack(side="left", padx=(0, 1))

        self.btnAniListLogin = ctk.CTkButton(self.anilist_panel, text="Giriş",
                                           command=self.on_anilist_login,
                                           fg_color="#ff6b6b", hover_color="#ff5252",
                                           width=50, height=32)
        self.btnAniListLogin.pack(side="left", padx=(0, 1))

        self.btnAniListLogout = ctk.CTkButton(self.anilist_panel, text="Çıkış",
                                            command=self.on_anilist_logout,
                                            fg_color="#666666", width=40, height=32)
        self.btnAniListLogout.pack(side="left", padx=(0, 1))

        # Kullanıcı adı label'ı (hover için)
        self.lblAniListUser = ctk.CTkLabel(self.anilist_panel, text="Giriş yapılmamış",
                                         font=ctk.CTkFont(size=9),
                                         text_color="#cccccc")
        self.lblAniListUser.pack(side="left", padx=(2, 2))

        # Avatar için image label (hover ile tooltip)
        self.avatarLabel = ctk.CTkLabel(self.anilist_panel, text="", width=28, height=28)
        self.avatarLabel.pack(side="left", padx=(0, 1))

        # Avatar'a hover efekti için
        self.avatarLabel.bind("<Enter>", self.show_user_tooltip)
        self.avatarLabel.bind("<Leave>", self.hide_user_tooltip)

        # Ayarlar butonu
        self.btnSettings = ctk.CTkButton(user_frame, text="⚙️", width=32, height=32,
                                       command=self.on_open_settings)
        self.btnSettings.pack(side="left")

        # AniList panelini başlangıçta gizle
        self.anilist_panel.pack_forget()
        self.anilist_visible = False

    def create_home_content(self):
        """Ana sayfa içeriği oluştur."""
        # Hero section
        self.create_hero_section()

        # Trend animeler bölümü
        self.create_trending_section()

        # Kategoriler
        self.create_categories_section()

    def create_hero_section(self):
        """Gelişmiş hero section oluştur - Netflix tarzı."""
        hero_frame = ctk.CTkFrame(self.content_area, fg_color="#1a1a1a", height=350,
                                corner_radius=15)
        hero_frame.pack(fill="x", pady=(0, 40))
        hero_frame.pack_propagate(False)

        # Gradient efekti için frame
        hero_content = ctk.CTkFrame(hero_frame, fg_color="transparent")
        hero_content.pack(fill="both", expand=True, padx=50, pady=30)

        # Sol taraf - Metin içeriği
        left_frame = ctk.CTkFrame(hero_content, fg_color="transparent")
        left_frame.pack(side="left", fill="both", expand=True)

        # Ana başlık
        title = ctk.CTkLabel(left_frame, text="🌟 Anime Dünyasını\nKeşfet",
                           font=ctk.CTkFont(size=42, weight="bold"),
                           text_color="#ffffff")
        title.pack(anchor="w", pady=(20, 15))

        # Alt başlık
        subtitle = ctk.CTkLabel(left_frame,
                              text="Binlerce anime arasından favorilerinizi bulun,\nizleme listenizi yönetin ve toplulukla paylaşın.\nAniList entegrasyonu ile keşiflerinizi kişiselleştirin.",
                              font=ctk.CTkFont(size=16),
                              text_color="#cccccc",
                              wraplength=550)
        subtitle.pack(anchor="w", pady=(0, 35))

        # İstatistikler
        stats_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        stats_frame.pack(anchor="w", pady=(0, 30))

        stats = [
            ("🎬", "10,000+", "Anime"),
            ("👥", "2M+", "Kullanıcı"),
            ("⭐", "4.5/5", "Ortalama Skor")
        ]

        for emoji, number, label in stats:
            stat_frame = ctk.CTkFrame(stats_frame, fg_color="#2a2a2a", width=100, height=60,
                                    corner_radius=8)
            stat_frame.pack(side="left", padx=(0, 15))
            stat_frame.pack_propagate(False)

            stat_emoji = ctk.CTkLabel(stat_frame, text=emoji, font=ctk.CTkFont(size=16))
            stat_emoji.pack(pady=(5, 0))

            stat_number = ctk.CTkLabel(stat_frame, text=number,
                                     font=ctk.CTkFont(size=14, weight="bold"),
                                     text_color="#ff6b6b")
            stat_number.pack()

            stat_label = ctk.CTkLabel(stat_frame, text=label,
                                    font=ctk.CTkFont(size=9),
                                    text_color="#888888")
            stat_label.pack()

        # Aksiyon butonları
        buttons_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        buttons_frame.pack(anchor="w")

        self.btnExplore = ctk.CTkButton(buttons_frame, text="🔥 Trendleri Keşfet",
                                      command=self.show_trending,
                                      fg_color="#ff6b6b", hover_color="#ff5252",
                                      width=180, height=50,
                                      font=ctk.CTkFont(size=15, weight="bold"),
                                      corner_radius=25)
        self.btnExplore.pack(side="left", padx=(0, 20))

        self.btnRandom = ctk.CTkButton(buttons_frame, text="🎲 Rastgele Anime",
                                     command=self.show_random_anime,
                                     fg_color="transparent", border_width=2,
                                     border_color="#4ecdc4", text_color="#4ecdc4",
                                     width=180, height=50,
                                     font=ctk.CTkFont(size=15, weight="bold"),
                                     corner_radius=25)
        self.btnRandom.pack(side="left")

        # Sağ taraf - Büyük görsel
        right_frame = ctk.CTkFrame(hero_content, fg_color="transparent")
        right_frame.pack(side="right", fill="both", expand=True)

        # Ana görsel için büyük alan
        hero_image_frame = ctk.CTkFrame(right_frame, fg_color="transparent", corner_radius=12)
        hero_image_frame.pack(expand=True)
        hero_image_frame.pack_propagate(False)

        # Hero görselini yükle
        try:
            icon_path = _resource_path(os.path.join('docs', 'TurkAnimu.png'))
            if os.path.exists(icon_path):
                # Open image
                pil_image = Image.open(icon_path)
                # Set frame size to 300x300
                hero_image_frame.configure(width=300, height=300)
                # Create CTkImage with size 300x300
                hero_image = ctk.CTkImage(pil_image, size=(300, 300))
                hero_label = ctk.CTkLabel(hero_image_frame, image=hero_image, text="")
                hero_label.pack(expand=True)
            else:
                # Fallback to text if icon not found
                hero_label = ctk.CTkLabel(hero_image_frame, text="🎬\nTÜRK\nANİMU",
                  font=ctk.CTkFont(size=48, weight="bold"),
                  text_color="#ff6b6b")
                hero_label.pack(expand=True)
        except Exception:
            # Fallback to text on error
            hero_label = ctk.CTkLabel(hero_image_frame, text="🎬\nTÜRK\nANİMU",
                  font=ctk.CTkFont(size=48, weight="bold"),
                  text_color="#ff6b6b")
            hero_label.pack(expand=True)

    def show_random_anime(self):
        """Rastgele anime göster."""
        self.message("Rastgele anime özelliği yakında eklenecek!")

    def create_trending_section(self):
        """Trend animeler bölümü oluştur."""
        section_frame = ctk.CTkFrame(self.content_area, fg_color="transparent")
        section_frame.pack(fill="x", pady=(0, 40))

        # Başlık ve açıklama
        title_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 25))

        section_title = ctk.CTkLabel(title_frame, text="🔥 Bu Hafta Trend",
                                   font=ctk.CTkFont(size=28, weight="bold"),
                                   text_color="#ffffff")
        section_title.pack(side="left")

        # Trend açıklama
        trend_desc = ctk.CTkLabel(title_frame, text="AniList topluluğunun en sevdiği animeler",
                                font=ctk.CTkFont(size=12),
                                text_color="#888888")
        trend_desc.pack(side="left", padx=(15, 0))

        self.btnViewAllTrending = ctk.CTkButton(title_frame, text="Tümünü Gör →",
                                              command=self.show_trending,
                                              fg_color="transparent", text_color="#ff6b6b",
                                              font=ctk.CTkFont(size=14, weight="bold"),
                                              hover_color="#ff5252")
        self.btnViewAllTrending.pack(side="right")

        # Trend animeler grid'i
        self.trending_grid = ctk.CTkFrame(section_frame, fg_color="transparent")
        self.trending_grid.pack(fill="both", expand=True, pady=(0, 12))

        # Loading state
        self.loading_label = ctk.CTkLabel(self.trending_grid, text="Trend animeler yükleniyor...",
                                        font=ctk.CTkFont(size=14),
                                        text_color="#888888")
        self.loading_label.pack(pady=50)

        # Trend animeleri yükle
        self.load_trending_anime()

    def create_categories_section(self):
        """Gelişmiş kategoriler bölümü oluştur."""
        section_frame = ctk.CTkFrame(self.content_area, fg_color="transparent")
        section_frame.pack(fill="x", pady=(0, 40))

        # Başlık
        section_title = ctk.CTkLabel(section_frame, text="🎯 Popüler Kategoriler",
                                   font=ctk.CTkFont(size=28, weight="bold"),
                                   text_color="#ffffff")
        section_title.pack(anchor="w", pady=(0, 25))

        # Kategori butonları - daha büyük ve şık
        categories_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        categories_frame.pack(fill="x")

        categories = [
            ("Aksiyon", "⚔️", "#ff6b6b", "Savaş ve macera dolu animeler"),
            ("Romantik", "💕", "#ff9ff3", "Aşk ve duygusal hikayeler"),
            ("Komedi", "😂", "#ffd93d", "Gülmece ve eğlence"),
            ("Fantastik", "🧙", "#a29bfe", "Büyü ve doğaüstü"),
            ("Bilim Kurgu", "🚀", "#74b9ff", "Gelecek ve teknoloji"),
            ("Dram", "🎭", "#fd79a8", "Duygusal ve derin hikayeler"),
            ("Mystery", "🔍", "#6c5ce7", "Gizem ve gerilim"),
            ("Horror", "👻", "#2d3436", "Korku ve dehşet")
        ]

        for i, (name, emoji, color, desc) in enumerate(categories):
            # Daha büyük kategori kartı
            cat_frame = ctk.CTkFrame(categories_frame, fg_color=color, width=140, height=100,
                                   corner_radius=12)
            cat_frame.pack(side="left", padx=12, pady=8)
            cat_frame.pack_propagate(False)

            # Hover efekti
            def on_enter(e, frame=cat_frame):
                frame.configure(fg_color=self.lighten_color(color))

            def on_leave(e, frame=cat_frame):
                frame.configure(fg_color=color)

            cat_frame.bind("<Enter>", on_enter)
            cat_frame.bind("<Leave>", on_leave)

            # Emoji
            cat_emoji = ctk.CTkLabel(cat_frame, text=emoji, font=ctk.CTkFont(size=24))
            cat_emoji.pack(pady=(8, 0))

            # İsim
            cat_label = ctk.CTkLabel(cat_frame, text=name,
                                   font=ctk.CTkFont(size=14, weight="bold"),
                                   text_color="#ffffff")
            cat_label.pack(pady=(2, 0))

            # Kısa açıklama
            cat_desc = ctk.CTkLabel(cat_frame, text=desc,
                                  font=ctk.CTkFont(size=8),
                                  text_color="#ffffff")
            cat_desc.pack(pady=(0, 8))

    def lighten_color(self, color):
        """Renk tonunu aç."""
        # Basit renk açma fonksiyonu
        if color == "#ff6b6b":
            return "#ff8a8a"
        elif color == "#ff9ff3":
            return "#ffb3f7"
        elif color == "#ffd93d":
            return "#ffe066"
        elif color == "#a29bfe":
            return "#b8bffe"
        elif color == "#74b9ff":
            return "#8fc1ff"
        elif color == "#fd79a8":
            return "#ff91b8"
        elif color == "#6c5ce7":
            return "#857ce8"
        elif color == "#2d3436":
            return "#454e50"
        else:
            return color

    def create_bottom_bar(self):
        """Alt bar oluştur."""
        bottom_frame = ctk.CTkFrame(self.main_container, fg_color="#1a1a1a", height=60)
        bottom_frame.pack(fill="x", side="bottom", padx=0, pady=0)
        bottom_frame.pack_propagate(False)

        # Sol taraf - Durum
        status_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        status_frame.pack(side="left", padx=20)

        self.status_label = ctk.CTkLabel(status_frame, text="TürkAnimu hazır",
                                       font=ctk.CTkFont(size=12),
                                       text_color="#cccccc")
        self.status_label.pack()

    def check_requirements_on_startup(self):
        """Eksik gereksinimleri kontrol et ve kullanıcıya bildir."""
        # Embed edilmiş araçlar kullanılıyor, kontrolü atla
        self.message("Embed edilmiş araçlar kullanılıyor", error=False)

    def show_requirements_dialog(self, missing_deps):
        """Eksik gereksinimler için dialog göster."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Gereksinimler Eksik")
        dialog.geometry("500x400")
        dialog.transient(self)
        dialog.grab_set()

        # Başlık
        title_label = ctk.CTkLabel(dialog, text="⚠️ Eksik Gereksinimler",
                                 font=ctk.CTkFont(size=18, weight="bold"))
        title_label.pack(pady=(20, 10))

        # Açıklama
        desc_text = f"Aşağıdaki gereksinimler bulunamadı:\n\n" + "\n".join(f"• {dep}" for dep in missing_deps)
        desc_text += "\n\nBu gereksinimler olmadan uygulama tam çalışmayabilir."
        desc_label = ctk.CTkLabel(dialog, text=desc_text, wraplength=450)
        desc_label.pack(pady=(0, 20))

        progress_label, progress_bar, buttons_frame = create_progress_section(dialog)

        def download_requirements():
            """Gereksinimleri indir."""
            download_btn.configure(state="disabled", text="İndiriliyor...")
            skip_btn.configure(state="disabled")

            def progress_callback(msg):
                progress_label.configure(text=msg)
                progress_bar.set(0.5)  # Orta değer

            def download_worker():
                try:
                    results = self.requirements_manager.download_requirements(missing_deps, progress_callback)

                    # Sonuçları göster
                    success_count = sum(1 for r in results if r["success"])
                    total_count = len(results)

                    if success_count == total_count:
                        progress_label.configure(text="✅ Tüm gereksinimler başarıyla kuruldu!")
                        progress_bar.set(1.0)
                        download_btn.configure(text="✅ Tamamlandı")
                    else:
                        failed = [r["name"] for r in results if not r["success"]]
                        progress_label.configure(text=f"❌ {len(failed)} gereksinim kurulamadı")
                        progress_bar.set(0.0)
                        download_btn.configure(text="❌ Hata Oluştu")

                    # 2 saniye sonra dialog'u kapat
                    self.after(2000, dialog.destroy)

                except Exception as e:
                    progress_label.configure(text=f"❌ Hata: {str(e)}")
                    progress_bar.set(0.0)
                    download_btn.configure(text="❌ Hata")

            threading.Thread(target=download_worker, daemon=True).start()

        download_btn = ctk.CTkButton(buttons_frame, text="⬇️ Gereksinimleri İndir",
                                   command=download_requirements,
                                   fg_color="#4ecdc4", hover_color="#45b7aa")
        download_btn.pack(side="left", padx=(0, 10))

        def skip_download():
            """İndirmeyi atla."""
            dialog.destroy()
            self.message("Gereksinimler indirilmedi. Bazı özellikler çalışmayabilir.", error=True)

        skip_btn = ctk.CTkButton(buttons_frame, text="⏭️ Atla",
                               command=skip_download,
                               fg_color="#666666")
        skip_btn.pack(side="left")

        # Dialog'u ortala
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
        y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

    def on_open_settings(self):
        """Ayarlar panelini içeride aç."""
        # Mevcut içeriği temizle
        self.clear_content_area()

        # Ayarlar paneli oluştur
        settings_frame = ctk.CTkFrame(self.content_area, fg_color="#2a2a2a")
        settings_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Başlık
        title_label = ctk.CTkLabel(settings_frame, text="⚙️ Ayarlar",
                                 font=ctk.CTkFont(size=24, weight="bold"),
                                 text_color="#ffffff")
        title_label.pack(pady=(20, 10))

        # Geri butonu
        back_btn = ctk.CTkButton(settings_frame, text="← Ana Sayfa",
                               command=self.show_home,
                               fg_color="transparent", text_color="#ff6b6b",
                               font=ctk.CTkFont(size=14, weight="bold"))
        back_btn.pack(anchor="nw", pady=(0, 20))

        # Ayarlar içeriği
        content_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Dosya ayarları
        self.dosya = Dosyalar()
        a = self.dosya.ayarlar

        # İndirme ayarları
        download_frame = ctk.CTkFrame(content_frame, fg_color="#1a1a1a")
        download_frame.pack(fill="x", pady=(0, 10))

        download_title = ctk.CTkLabel(download_frame, text="İndirme Ayarları",
                                    font=ctk.CTkFont(size=16, weight="bold"))
        download_title.pack(pady=(10, 5))

        # Paralel indirme sayısı
        parallel_frame = ctk.CTkFrame(download_frame, fg_color="transparent")
        parallel_frame.pack(fill="x", padx=10, pady=5)

        parallel_label = ctk.CTkLabel(parallel_frame, text="Paralel indirme sayısı:")
        parallel_label.pack(side="left")

        self.spinParallel = ctk.CTkEntry(parallel_frame, width=100)
        self.spinParallel.pack(side="right")
        self.spinParallel.insert(0, str(a.get("paralel indirme sayisi", 3)))

        # Maksimum çözünürlük
        maxres_frame = ctk.CTkFrame(download_frame, fg_color="transparent")
        maxres_frame.pack(fill="x", padx=10, pady=5)

        self.chkMaxRes = ctk.CTkCheckBox(maxres_frame, text="Maksimum çözünürlük")
        self.chkMaxRes.pack(side="left")
        self.chkMaxRes.select() if a.get("max resolution", True) else None

        # 1080p aday sayısı
        early_frame = ctk.CTkFrame(download_frame, fg_color="transparent")
        early_frame.pack(fill="x", padx=10, pady=5)

        early_label = ctk.CTkLabel(early_frame, text="1080p aday sayısı:")
        early_label.pack(side="left")

        self.spinEarlySubset = ctk.CTkEntry(early_frame, width=100)
        self.spinEarlySubset.pack(side="right")
        self.spinEarlySubset.insert(0, str(a.get("1080p aday sayısı", 8)))

        # Aria2c kullan
        aria_frame = ctk.CTkFrame(download_frame, fg_color="transparent")
        aria_frame.pack(fill="x", padx=10, pady=(5, 10))

        self.chkAria2 = ctk.CTkCheckBox(aria_frame, text="Aria2c kullan")
        self.chkAria2.pack(side="left")
        self.chkAria2.select() if a.get("aria2c kullan", False) else None

        # Oynatma ayarları
        play_frame = ctk.CTkFrame(content_frame, fg_color="#1a1a1a")
        play_frame.pack(fill="x", pady=(0, 10))

        play_title = ctk.CTkLabel(play_frame, text="Oynatma Ayarları",
                                font=ctk.CTkFont(size=16, weight="bold"))
        play_title.pack(pady=(10, 5))

        # Manuel fansub seçimi
        manual_frame = ctk.CTkFrame(play_frame, fg_color="transparent")
        manual_frame.pack(fill="x", padx=10, pady=5)

        self.chkManuel = ctk.CTkCheckBox(manual_frame, text="Manuel fansub seçimi")
        self.chkManuel.pack(side="left")
        self.chkManuel.select() if a.get("manuel fansub", False) else None

        # İzlerken kaydet
        save_frame = ctk.CTkFrame(play_frame, fg_color="transparent")
        save_frame.pack(fill="x", padx=10, pady=5)

        self.chkSaveWhileWatch = ctk.CTkCheckBox(save_frame, text="İzlerken kaydet")
        self.chkSaveWhileWatch.pack(side="left")
        self.chkSaveWhileWatch.select() if a.get("izlerken kaydet", False) else None

        # Dakika hatırla
        minute_frame = ctk.CTkFrame(play_frame, fg_color="transparent")
        minute_frame.pack(fill="x", padx=10, pady=(5, 10))

        self.chkRememberMin = ctk.CTkCheckBox(minute_frame, text="Kaldığın dakikayı hatırla")
        self.chkRememberMin.pack(side="left")
        self.chkRememberMin.select() if a.get("dakika hatirla", True) else None

        # AniList OAuth ayarları
        anilist_frame = ctk.CTkFrame(content_frame, fg_color="#1a1a1a")
        anilist_frame.pack(fill="x", pady=(0, 10))

        anilist_title = ctk.CTkLabel(anilist_frame, text="AniList OAuth Ayarları",
                                   font=ctk.CTkFont(size=16, weight="bold"))
        anilist_title.pack(pady=(10, 5))

        # client_id
        row_client_id = ctk.CTkFrame(anilist_frame, fg_color="transparent")
        row_client_id.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(row_client_id, text="Client ID:").pack(side="left")
        self.txtAniClientId = ctk.CTkEntry(row_client_id, width=280)
        self.txtAniClientId.pack(side="right")
        try:
            from turkanime_api.anilist_client import anilist_client as _ac
            self.txtAniClientId.insert(0, str(getattr(_ac, 'client_id', '')))
        except Exception:
            pass

        # client_secret
        row_client_secret = ctk.CTkFrame(anilist_frame, fg_color="transparent")
        row_client_secret.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(row_client_secret, text="Client Secret:").pack(side="left")
        self.txtAniClientSecret = ctk.CTkEntry(row_client_secret, width=280)
        self.txtAniClientSecret.pack(side="right")
        try:
            self.txtAniClientSecret.insert(0, str(getattr(_ac, 'client_secret', '')))
        except Exception:
            pass

        # redirect_uri
        row_redirect = ctk.CTkFrame(anilist_frame, fg_color="transparent")
        row_redirect.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(row_redirect, text="Redirect URI:").pack(side="left")
        self.txtAniRedirect = ctk.CTkEntry(row_redirect, width=280)
        self.txtAniRedirect.pack(side="right")
        try:
            self.txtAniRedirect.insert(0, str(getattr(_ac, 'redirect_uri', 'http://localhost:9921/anilist-login')))
        except Exception:
            self.txtAniRedirect.insert(0, 'http://localhost:9921/anilist-login')

        # Yardım notu
        help_lbl = ctk.CTkLabel(anilist_frame,
                              text="Not: AniList uygulama ayarındaki Redirect URL ile burada yazan aynı olmalı. Girişte hata alırsanız bu alanı kontrol edin.",
                              text_color="#cccccc", wraplength=600, font=ctk.CTkFont(size=11))
        help_lbl.pack(padx=10, pady=(0, 10))

        # Arayüz ayarları
        ui_frame = ctk.CTkFrame(content_frame, fg_color="#1a1a1a")
        ui_frame.pack(fill="x", pady=(0, 10))

        ui_title = ctk.CTkLabel(ui_frame, text="Arayüz Ayarları",
                              font=ctk.CTkFont(size=16, weight="bold"))
        ui_title.pack(pady=(10, 5))

        # İzlendi/İndirildi ikonu
        icon_frame = ctk.CTkFrame(ui_frame, fg_color="transparent")
        icon_frame.pack(fill="x", padx=10, pady=(5, 10))

        self.chkWatchedIcon = ctk.CTkCheckBox(icon_frame, text="İzlendi/İndirildi ikonu")
        self.chkWatchedIcon.pack(side="left")
        self.chkWatchedIcon.select() if a.get("izlendi ikonu", True) else None

        # İndirilenler klasörü
        folder_frame = ctk.CTkFrame(content_frame, fg_color="#1a1a1a")
        folder_frame.pack(fill="x", pady=(0, 20))

        folder_title = ctk.CTkLabel(folder_frame, text="Klasör Ayarları",
                                  font=ctk.CTkFont(size=16, weight="bold"))
        folder_title.pack(pady=(10, 5))

        folder_input_frame = ctk.CTkFrame(folder_frame, fg_color="transparent")
        folder_input_frame.pack(fill="x", padx=10, pady=5)

        self.txtDownloads = ctk.CTkEntry(folder_input_frame, width=300)
        self.txtDownloads.pack(side="left", padx=(0, 10))
        self.txtDownloads.insert(0, a.get("indirilenler", "."))

        btnBrowse = ctk.CTkButton(folder_input_frame, text="Seç…",
                                command=self.on_choose_dir)
        btnBrowse.pack(side="left")

        # Discord Rich Presence ayarları
        discord_frame = ctk.CTkFrame(content_frame, fg_color="#1a1a1a")
        discord_frame.pack(fill="x", pady=(0, 20))

        discord_title = ctk.CTkLabel(discord_frame, text="Discord Rich Presence",
                                   font=ctk.CTkFont(size=16, weight="bold"))
        discord_title.pack(pady=(10, 5))

        discord_check_frame = ctk.CTkFrame(discord_frame, fg_color="transparent")
        discord_check_frame.pack(fill="x", padx=10, pady=(5, 10))

        self.chkDiscordRPC = ctk.CTkCheckBox(discord_check_frame, text="Discord Rich Presence'i etkinleştir")
        self.chkDiscordRPC.pack(side="left")
        self.chkDiscordRPC.select() if a.get("discord_rich_presence", True) else None

        # Güncelleme ayarları
        update_frame = ctk.CTkFrame(content_frame, fg_color="#1a1a1a")
        update_frame.pack(fill="x", pady=(0, 20))

        update_title = ctk.CTkLabel(update_frame, text="Güncelleme Ayarları",
                                  font=ctk.CTkFont(size=16, weight="bold"))
        update_title.pack(pady=(10, 5))

        update_check_frame = ctk.CTkFrame(update_frame, fg_color="transparent")
        update_check_frame.pack(fill="x", padx=10, pady=(5, 10))

        btnCheckUpdate = ctk.CTkButton(update_check_frame, text="🔄 Güncelleme Kontrolü",
                                     command=self.on_check_update,
                                     fg_color="#4ecdc4", hover_color="#45b7aa")
        btnCheckUpdate.pack(side="left")

        # Butonlar
        buttons_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=20, pady=(0, 20))

        btnSave = ctk.CTkButton(buttons_frame, text="💾 Kaydet",
                              command=self.on_save_settings,
                              fg_color="#4ecdc4", hover_color="#45b7aa",
                              width=120, height=40)
        btnSave.pack(side="left", padx=(0, 10))

        btnCancel = ctk.CTkButton(buttons_frame, text="❌ İptal",
                                command=self.show_home,
                                fg_color="#666666", width=120, height=40)
        btnCancel.pack(side="left")

        # AniList yardımcı butonları (ayar ekranında alt kısım)
        al_buttons = ctk.CTkFrame(settings_frame, fg_color="transparent")
        al_buttons.pack(fill="x", padx=20, pady=(0, 10))
        btnOpenLogin = ctk.CTkButton(al_buttons, text="🔗 Giriş Sayfasını Aç",
                                  command=lambda: webbrowser.open(anilist_client.get_auth_url(response_type="code")),
                                  fg_color="#ff6b6b", hover_color="#ff5252")
        btnOpenLogin.pack(side="left")
        btnClearTok = ctk.CTkButton(al_buttons, text="🧹 Token Temizle",
                                  command=lambda: (anilist_client.clear_tokens(), self.check_anilist_auth_status(), self.message("Token temizlendi")),
                                  fg_color="#666666")
        btnClearTok.pack(side="left", padx=(10,0))

    def on_check_update(self):
        """Güncelleme kontrolünü başlat."""
        def worker():
            try:
                self.message("Güncellemeler kontrol ediliyor…")
                if hasattr(self, "update_manager") and self.update_manager:
                    # Farklı olası metod adlarını dene
                    for meth in ("check_for_updates", "check_updates", "check_update", "run_update_check"):
                        fn = getattr(self.update_manager, meth, None)
                        if callable(fn):
                            fn()
                            return
                    # Yedek: sürümler sayfasını aç
                    webbrowser.open("https://github.com/barkeser2002/turkanime-indirici/releases")
                    self.message("Güncellemeler sayfasına yönlendirildi", error=False)
                else:
                    self.message("Güncelleme yöneticisi bulunamadı", error=True)
            except Exception as e:
                self.message(f"Güncelleme kontrolü hatası: {e}", error=True)
        threading.Thread(target=worker, daemon=True).start()

    def on_choose_dir(self):
        """İndirilenler klasörü seç."""
        d = filedialog.askdirectory()
        if d:
            self.txtDownloads.delete(0, "end")
            self.txtDownloads.insert(0, d)

    def on_save_settings(self):
        """Ayarları kaydet."""
        try:
            self.dosya.set_ayar("manuel fansub", self.chkManuel.get())
            self.dosya.set_ayar("izlerken kaydet", self.chkSaveWhileWatch.get())
            self.dosya.set_ayar("izlendi ikonu", self.chkWatchedIcon.get())
            self.dosya.set_ayar("paralel indirme sayisi", int(self.spinParallel.get()))
            self.dosya.set_ayar("max resolution", self.chkMaxRes.get())
            self.dosya.set_ayar("1080p aday sayısı", int(self.spinEarlySubset.get()))
            self.dosya.set_ayar("dakika hatirla", self.chkRememberMin.get())
            self.dosya.set_ayar("aria2c kullan", self.chkAria2.get())
            self.dosya.set_ayar("indirilenler", self.txtDownloads.get())
            self.dosya.set_ayar("discord_rich_presence", self.chkDiscordRPC.get())

            # Discord Rich Presence ayarını uygula
            if self.chkDiscordRPC.get():
                if not self.discord_connected:
                    self.init_discord_rpc()
                    if self.discord_connected:
                        self.message("Discord Rich Presence açıldı", error=False)
            else:
                if self.discord_connected:
                    self.disconnect_discord_rpc()
                    self.message("Discord Rich Presence kapatıldı", error=False)

            # AniList OAuth ayarlarını uygula
            try:
                cid = self.txtAniClientId.get().strip()
                csec = self.txtAniClientSecret.get().strip()
                ruri = self.txtAniRedirect.get().strip()
                if cid and ruri:
                    anilist_client.set_oauth_config(cid, csec, ruri)
            except Exception as e:
                self.message(f"AniList ayarları kaydedilirken hata: {e}", error=True)

            self.message("Ayarlar kaydedildi!")
            self.show_home()
        except ValueError as e:
            self.message(f"Ayar kaydetme hatası: {str(e)}")

    def load_trending_anime(self):
        """Trend animeleri yükle."""
        def load_worker():
            try:
                trending = anilist_client.get_trending_anime(page=1, per_page=12)
                self.after(0, lambda: self.display_trending_anime(trending))
            except Exception as e:
                self.after(0, lambda: self.show_trending_error(str(e)))

        threading.Thread(target=load_worker, daemon=True).start()

    def display_trending_anime(self, anime_list):
        """Trend animeleri göster."""
        # Loading label'ı kaldır
        if hasattr(self, 'loading_label'):
            self.loading_label.destroy()

        # Grid oluştur - responsive sütun sayısı
        row = 0
        col = 0
        max_cols = 6  # 6'dan 5'e düşürdük, kartlar daha büyük görünsün

        for anime in anime_list[:12]: # 12'den 10'a düşürdük, daha az ama daha büyük kart
            if col >= max_cols:
                col = 0
                row += 1

            # Anime kartı
            self.create_anime_card(self.trending_grid, anime, row, col, max_cols)
            col += 1

    def create_anime_card(self, parent, anime_data, row, col, max_cols):
        """Gelişmiş anime kartı oluştur - Netflix tarzı."""
        # Daha büyük ve şık kart - genişlik artırıldı
        card_width = 220 if max_cols == 5 else 200  # 5 sütun için daha geniş
        card_frame = ctk.CTkFrame(parent, fg_color="#1a1a1a", width=card_width, height=340,
                                border_width=1, border_color="#333333",
                                corner_radius=12)
        card_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nw")  # padding azaltıldı
        card_frame.pack_propagate(False)

        # Gelişmiş hover efekti
        def on_enter(e):
            card_frame.configure(fg_color="#2a2a2a", border_color="#ff6b6b")

        def on_leave(e):
            card_frame.configure(fg_color="#1a1a1a", border_color="#333333")

        card_frame.bind("<Enter>", on_enter)
        card_frame.bind("<Leave>", on_leave)

        # Büyük kapak görseli - optimize edilmiş boyut
        cover_width = 200 if max_cols == 5 else 180
        cover_height = 260 if max_cols == 5 else 240
        cover_frame = ctk.CTkFrame(card_frame, fg_color="#0f0f0f", width=cover_width, height=cover_height,
                                 corner_radius=8)
        cover_frame.pack(pady=(15, 0))
        cover_frame.pack_propagate(False)

        # Kapak görseli için optimize edilmiş alan
        cover_label = ctk.CTkLabel(cover_frame, text="", font=ctk.CTkFont(size=60),
                                 text_color="#666666")
        cover_label.pack(expand=True)

        # Kapak görselini yükle (optimize edilmiş boyut)
        img_width = 180 if max_cols == 5 else 160
        img_height = 240 if max_cols == 5 else 220
        cover_url = anime_data.get('coverImage', {}).get('large')
        if cover_url:
            self.load_anilist_thumbnail(cover_url, cover_label, img_width, img_height)

        # Başlık - geliştirilmiş format
        title_text = anime_data.get('title', {}).get('romaji', 'Unknown')
        # Daha akıllı başlık kısaltma
        if len(title_text) > 22:
            title_text = title_text[:19] + "..."
        elif len(title_text) > 18:
            title_text = title_text[:15] + "..."

        wrap_width = 190 if max_cols == 5 else 170
        title_label = ctk.CTkLabel(card_frame, text=title_text,
                                 font=ctk.CTkFont(size=11, weight="bold"),
                                 text_color="#ffffff", wraplength=wrap_width,
                                 justify="center")
        title_label.pack(pady=(10, 0))

        # Skor ve bilgiler - yeniden düzenlenmiş
        info_padding = 10 if max_cols == 5 else 8
        info_frame = ctk.CTkFrame(card_frame, fg_color="transparent")
        info_frame.pack(fill="x", padx=info_padding, pady=(6, 8))

        # Skor - daha küçük ve şık
        score = anime_data.get('averageScore', 0)
        if score:
            score_frame = ctk.CTkFrame(info_frame, fg_color="#ff6b6b", width=35, height=18,
                                     corner_radius=8)
            score_frame.pack(side="left")
            score_frame.pack_propagate(False)

            score_label = ctk.CTkLabel(score_frame, text=f"★{score}",
                                     font=ctk.CTkFont(size=8, weight="bold"),
                                     text_color="#ffffff")
            score_label.pack()

        # Popülerlik/Bölüm sayısı - daha küçük font
        popularity = anime_data.get('episodes', 0)
        if popularity:
            ep_label = ctk.CTkLabel(info_frame, text=f"{popularity} bölüm",
                                  font=ctk.CTkFont(size=8),
                                  text_color="#cccccc")
            ep_label.pack(side="right")

        # Tıkla eventi - tüm alan tıklanabilir
        def on_click():
            self.show_anime_details(anime_data)



        card_frame.bind("<Button-1>", lambda e: on_click())
        cover_label.bind("<Button-1>", lambda e: on_click())
        title_label.bind("<Button-1>", lambda e: on_click())

    def show_anime_details(self, anime_data):
        """Anime detaylarını göster."""
        # Detay görünümü oluştur
        self.clear_content_area()
    # Seçili animeyi sakla (global oynat/indir butonları için)
        self.selected_anime = anime_data

        # Discord Rich Presence güncelle - AniList button'u ile
        anime_title = anime_data.get('title', {}).get('romaji', 'Bilinmeyen Anime')
        anilist_id = anime_data.get('id')
        
        buttons = [
            {
                "label": "Uygulamayı Edin",
                "url": "https://github.com/barkeser2002/turkanime-indirici/releases"
            }
        ]
        
        if anilist_id:
            buttons.append({
                "label": "AniList'te Gör",
                "url": f"https://anilist.co/anime/{anilist_id}"
            })
        
        self.update_discord_presence(f"{anime_title} detaylarına bakıyor", "TürkAnimu GUI", buttons=buttons)

        details_frame = ctk.CTkFrame(self.content_area, fg_color="transparent")
        details_frame.pack(fill="both", expand=True)

        # Geri butonu
        back_btn = ctk.CTkButton(details_frame, text="← Geri",
                               command=self.show_home,
                               fg_color="transparent", text_color="#ff6b6b",
                               font=ctk.CTkFont(size=14, weight="bold"))
        back_btn.pack(anchor="nw", pady=(10, 20), padx=10)

        # Ana içerik
        content_frame = ctk.CTkFrame(details_frame, fg_color="#2a2a2a")
        content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Sol taraf - Kapak ve bilgiler
        left_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        left_frame.pack(side="left", fill="y", padx=(20, 40), pady=20)

        # Büyük kapak
        cover_frame = ctk.CTkFrame(left_frame, fg_color="#1a1a1a", width=250, height=350)
        cover_frame.pack(pady=(0, 20))
        cover_frame.pack_propagate(False)

        cover_label = ctk.CTkLabel(cover_frame, text="", font=ctk.CTkFont(size=100))
        cover_label.pack(expand=True)

        cover_url = anime_data.get('coverImage', {}).get('large')
        if cover_url:
            self.load_anilist_thumbnail(cover_url, cover_label, 230, 330)

        # Anime bilgileri
        info_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        info_frame.pack(fill="x")

        title = anime_data.get('title', {}).get('romaji', 'Unknown')
        title_label = ctk.CTkLabel(info_frame, text=title,
                                 font=ctk.CTkFont(size=24, weight="bold"),
                                 text_color="#ffffff", wraplength=300)
        title_label.pack(anchor="w", pady=(0, 10))

        # Meta bilgiler
        meta_info = []
        if anime_data.get('episodes'):
            meta_info.append(f"📺 {anime_data['episodes']} bölüm")
        if anime_data.get('duration'):
            meta_info.append(f"⏱️ {anime_data['duration']} dk")
        if anime_data.get('season'):
            meta_info.append(f"📅 {anime_data['season']} {anime_data.get('seasonYear', '')}")

        if meta_info:
            meta_label = ctk.CTkLabel(info_frame, text=" • ".join(meta_info),
                                    font=ctk.CTkFont(size=12),
                                    text_color="#cccccc")
            meta_label.pack(anchor="w", pady=(0, 15))

        # Skor ve popülerlik
        stats_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        stats_frame.pack(fill="x", pady=(0, 20))

        score = anime_data.get('averageScore', 0)
        if score:
            score_frame = ctk.CTkFrame(stats_frame, fg_color="#333333", width=80, height=60)
            score_frame.pack(side="left", padx=(0, 10))
            score_frame.pack_propagate(False)

            score_title = ctk.CTkLabel(score_frame, text="SKOR",
                                     font=ctk.CTkFont(size=10),
                                     text_color="#cccccc")
            score_title.pack(pady=(5, 0))

            score_value = ctk.CTkLabel(score_frame, text=f"{score}%",
                                     font=ctk.CTkFont(size=18, weight="bold"),
                                     text_color="#ffd93d")
            score_value.pack()

        popularity = anime_data.get('popularity', 0)
        if popularity:
            pop_frame = ctk.CTkFrame(stats_frame, fg_color="#333333", width=80, height=60)
            pop_frame.pack(side="left", padx=(0, 10))
            pop_frame.pack_propagate(False)

            pop_title = ctk.CTkLabel(pop_frame, text="POPÜLER",
                                   font=ctk.CTkFont(size=10),
                                   text_color="#cccccc")
            pop_title.pack(pady=(5, 0))

            pop_value = ctk.CTkLabel(pop_frame, text=f"#{popularity}",
                                   font=ctk.CTkFont(size=16, weight="bold"),
                                   text_color="#74b9ff")
            pop_value.pack()

        # Aksiyon butonları
        buttons_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", pady=(20, 0))

        self.btnAddToList = ctk.CTkButton(buttons_frame, text="➕ Listeye Ekle",
                                        command=lambda: self.add_anilist_to_library(anime_data),
                                        fg_color="#ff6b6b", hover_color="#ff5252",
                                        width=120, height=40)
        self.btnAddToList.pack(side="left", padx=(0, 10))

        self.btnSearchLocal = ctk.CTkButton(buttons_frame, text="🔍 Yerelde Ara",
                                          command=lambda: self.search_anime_locally(title),
                                          fg_color="#4ecdc4", hover_color="#45b7aa",
                                          width=120, height=40)
        self.btnSearchLocal.pack(side="left", padx=(0, 10))

        # AniList sayfası butonu
        anilist_id = anime_data.get('id')
        if anilist_id:
            self.btnAniListPage = ctk.CTkButton(buttons_frame, text="🌐 AniList",
                                              command=lambda: self.open_anilist_page(anilist_id),
                                              fg_color="#02a9ff", hover_color="#0099e5",
                                              width=100, height=40)
            self.btnAniListPage.pack(side="left")

        # Sağ taraf - Özet ve detaylar
        right_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        right_frame.pack(side="right", fill="both", expand=True, padx=(0, 20), pady=20)

        # Özet
        summary_title = ctk.CTkLabel(right_frame, text="📖 Özet",
                                   font=ctk.CTkFont(size=18, weight="bold"),
                                   text_color="#ffffff")
        summary_title.pack(anchor="w", pady=(0, 10))

        description = anime_data.get('description', 'Özet bulunamadı.')
        # HTML taglerini temizle
        import re
        description = re.sub(r'<[^>]+>', '', description)

        summary_textbox = ctk.CTkTextbox(right_frame, wrap="word", height=200)
        summary_textbox.pack(fill="x", pady=(0, 20))
        summary_textbox.insert("0.0", description)
        summary_textbox.configure(state="disabled")

        # Türler
        if anime_data.get('genres'):
            genres_title = ctk.CTkLabel(right_frame, text="🏷️ Türler",
                                      font=ctk.CTkFont(size=16, weight="bold"),
                                      text_color="#ffffff")
            genres_title.pack(anchor="w", pady=(0, 10))

            genres_text = ", ".join(anime_data['genres'])
            genres_label = ctk.CTkLabel(right_frame, text=genres_text,
                                      font=ctk.CTkFont(size=12),
                                      text_color="#cccccc", wraplength=400)
            genres_label.pack(anchor="w", pady=(0, 20))

        # Stüdyolar
        if anime_data.get('studios', {}).get('nodes'):
            studios_title = ctk.CTkLabel(right_frame, text="🎬 Stüdyo",
                                       font=ctk.CTkFont(size=16, weight="bold"),
                                       text_color="#ffffff")
            studios_title.pack(anchor="w", pady=(0, 10))

            studios_text = ", ".join([s['name'] for s in anime_data['studios']['nodes']])
            studios_label = ctk.CTkLabel(right_frame, text=studios_text,
                                       font=ctk.CTkFont(size=12),
                                       text_color="#cccccc")
            studios_label.pack(anchor="w")

        # Bölümler bölümü (AnimeciX üzerinden)
        episodes_section = ctk.CTkFrame(details_frame, fg_color="transparent")
        episodes_section.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        ep_title_row = ctk.CTkFrame(episodes_section, fg_color="transparent")
        ep_title_row.pack(fill="x")
        ep_title = ctk.CTkLabel(ep_title_row, text="📺 Bölümler",
                               font=ctk.CTkFont(size=18, weight="bold"),
                               text_color="#ffffff")
        ep_title.pack(side="left")

        # Toplu aksiyon butonları
        bulk_actions = ctk.CTkFrame(ep_title_row, fg_color="transparent")
        bulk_actions.pack(side="right")
        btnPlayFirst = ctk.CTkButton(bulk_actions, text="▶️ İlk Seçiliyi Oynat",
                                     width=160, height=34,
                                     command=lambda: self._play_first_selected_episode())
        btnPlayFirst.pack(side="left", padx=(0, 8))
        btnDlSel = ctk.CTkButton(bulk_actions, text="⬇️ Seçilenleri İndir",
                                 width=160, height=34,
                                 command=lambda: self._download_selected_episodes())
        btnDlSel.pack(side="left", padx=(0, 8))
        btnSearchAgain = ctk.CTkButton(bulk_actions, text="🔍 İstediğin Anime Değil Mi?",
                                      width=180, height=34,
                                      command=lambda: self._search_anime_again())
        btnSearchAgain.pack(side="left")

        # Liste alanı
        self.episodes_vars = []  # [(var, obj)]
        self.episodes_objs = []
        self.episodes_list = ctk.CTkFrame(episodes_section, fg_color="#1a1a1a")
        self.episodes_list.pack(fill="both", expand=True, pady=(10, 0))

        # Sonsuz scroll için değişkenler
        self.episodes_loaded = 0
        self.episodes_per_page = 20
        self.is_loading_episodes = False
        self.all_episodes = []  # Tüm bölümler burada saklanacak

        ep_loading = ctk.CTkLabel(self.episodes_list, text="Bölümler yükleniyor…",
                                  font=ctk.CTkFont(size=14), text_color="#cccccc")
        ep_loading.pack(pady=20)

        # Başlık adayı: romaji -> english fallback
        romaji = anime_data.get('title', {}).get('romaji') or ""
        english = anime_data.get('title', {}).get('english') or ""
        query_title = romaji if romaji else english

        def load_eps_worker():
            try:
                # Tüm bölümleri yükle
                all_items = []
                if self.selected_source == "TürkAnime":
                    # TürkAnime'de ara
                    from turkanime_api.objects import Anime
                    all_list = Anime.get_anime_listesi()
                    pick = None
                    for slug, name in all_list:
                        if str(name).strip().lower() == query_title.strip().lower():
                            pick = (slug, name)
                            break
                    if not pick and all_list:
                        # İlk sonucu al
                        pick = all_list[0]
                    
                    if pick:
                        slug, name = pick
                        ani = Anime(slug)
                        bolumler = ani.bolumler
                        for b in bolumler:
                            all_items.append({"title": b.title, "obj": b})
                else:
                    # AnimeciX'te ara
                    results = search_animecix(query_title)
                    pick = None
                    if results:
                        # Önce exact eşleşme ara (case-insensitive)
                        for _id, name in results:
                            if str(name).strip().lower() == query_title.strip().lower():
                                pick = (_id, name)
                                break
                        if not pick:
                            pick = results[0]
                    
                    if pick:
                        _id, name = pick
                        cix = CixAnime(id=int(_id), title=str(name))
                        eps = cix.episodes
                        ada = AdapterAnime(slug=str(cix.id), title=cix.title)
                        for e in eps:
                            ab = AdapterBolum(url=e.url, title=e.title, anime=ada)
                            all_items.append({"title": e.title, "obj": ab})

                # Bölümleri sakla ve render et
                self.all_episodes = all_items
                self.after(0, lambda: self.render_episodes_page())
            except Exception as e:
                def render_err():
                    try:
                        ep_loading.configure(text=f"Hata: {e}", text_color="#ff6b6b")
                    except Exception:
                        pass
                self.after(0, render_err)

        threading.Thread(target=load_eps_worker, daemon=True).start()

    # --- Bölüm oynatma/indirme yardımcıları ---
    def _play_episode(self, episode_obj):
        def worker():
            try:
                vf = VideoFindWorker(episode_obj)
                vf.signals.connect_found(self.play_video)
                vf.signals.connect_error(lambda msg: self.message(f"Hata: {msg}", error=True))
                vf.run()
            except Exception as e:
                self.message(f"Video arama hatası: {e}", error=True)
        threading.Thread(target=worker, daemon=True).start()

    def _download_episode(self, episode_obj):
        def worker():
            try:
                # Discord Rich Presence güncelle
                if episode_obj and episode_obj.anime:
                    anime_title = episode_obj.anime.title
                    episode_title = episode_obj.title
                    self.update_discord_presence_download(anime_title, "0")
                
                dw = DownloadWorker([episode_obj])
                dw.signals.connect_progress(lambda msg: self.status_label.configure(text=msg))
                dw.signals.connect_success(lambda: self.message("İndirme tamamlandı!"))
                dw.signals.connect_error(lambda msg: self.message(f"İndirme hatası: {msg}", error=True))
                dw.run()
            except Exception as e:
                self.message(f"İndirme başlatılamadı: {e}", error=True)
        threading.Thread(target=worker, daemon=True).start()

    def _play_first_selected_episode(self):
        if not getattr(self, 'episodes_vars', None):
            self.message("Seçili bölüm yok", error=True)
            return
        for var, obj in self.episodes_vars:
            if var.get():
                self._play_episode(obj)
                return
        self.message("Önce bölüm seçin", error=True)

    def _search_anime_again(self):
        """Mevcut kaynak ile anime'yi yeniden ara ve bölümleri yükle."""
        if not hasattr(self, 'selected_anime') or not self.selected_anime:
            self.message("Önce bir anime seçin", error=True)
            return

        # Mevcut anime bilgilerini al
        anime_data = self.selected_anime
        romaji = anime_data.get('title', {}).get('romaji') or ""
        english = anime_data.get('title', {}).get('english') or ""
        query_title = romaji if romaji else english

        if not query_title:
            self.message("Anime başlığı bulunamadı", error=True)
            return

        # Bölümler alanını temizle ve yükleniyor mesajı göster
        for widget in self.episodes_list.winfo_children():
            widget.destroy()

        loading_label = ctk.CTkLabel(self.episodes_list, text="Anime yeniden aranıyor...",
                                   font=ctk.CTkFont(size=14), text_color="#cccccc")
        loading_label.pack(pady=20)

        def search_worker():
            try:
                # Mevcut kaynak ile arama yap
                all_items = []
                if self.selected_source == "TürkAnime":
                    # TürkAnime'de ara
                    from turkanime_api.objects import Anime
                    all_list = Anime.get_anime_listesi()
                    pick = None
                    for slug, name in all_list:
                        if str(name).strip().lower() == query_title.strip().lower():
                            pick = (slug, name)
                            break
                    if not pick and all_list:
                        # İlk sonucu al
                        pick = all_list[0]

                    if pick:
                        slug, name = pick
                        ani = Anime(slug)
                        bolumler = ani.bolumler
                        for b in bolumler:
                            all_items.append({"title": b.title, "obj": b})
                else:
                    # AnimeciX'te ara
                    results = search_animecix(query_title)
                    pick = None
                    if results:
                        # Önce exact eşleşme ara (case-insensitive)
                        for _id, name in results:
                            if str(name).strip().lower() == query_title.strip().lower():
                                pick = (_id, name)
                                break
                        if not pick:
                            pick = results[0]
                    
                    if pick:
                        _id, name = pick
                        cix = CixAnime(id=int(_id), title=str(name))
                        eps = cix.episodes
                        ada = AdapterAnime(slug=str(cix.id), title=cix.title)
                        for e in eps:
                            ab = AdapterBolum(url=e.url, title=e.title, anime=ada)
                            all_items.append({"title": e.title, "obj": ab})

                # Bölümleri sakla ve render et
                self.all_episodes = all_items
                self.after(0, lambda: self.render_episodes_page())

            except Exception as e:
                def render_error():
                    try:
                        loading_label.configure(text=f"Hata: {e}", text_color="#ff6b6b")
                    except Exception:
                        pass
                self.after(0, render_error)

        threading.Thread(target=search_worker, daemon=True).start()

    def _download_selected_episodes(self):
        if not getattr(self, 'episodes_vars', None):
            self.message("Seçili bölüm yok", error=True)
            return
        selected = [obj for var, obj in self.episodes_vars if var.get()]
        if not selected:
            # If no episodes are selected, fall back to the first episode or show an error
            if getattr(self, 'episodes_objs', None) and self.episodes_objs:
                selected = [self.episodes_objs[0]]  # Select the first episode as fallback
            else:
                self.message("İndirilecek bölüm bulunamadı", error=True)
                return
        
        def worker():
            try:
                # Discord Rich Presence güncelle
                if selected and selected[0].anime:
                    anime_title = selected[0].anime.title
                    episode_count = len(selected)
                    self.update_discord_presence_download(anime_title, "0")
                
                dw = DownloadWorker(selected, update_callback=self.update_downloaded_list)
                dw.signals.connect_progress(lambda msg: self.status_label.configure(text=msg))
                dw.signals.connect_success(lambda: self.message("İndirme tamamlandı!"))
                dw.signals.connect_error(lambda msg: self.message(f"İndirme hatası: {msg}", error=True))
                dw.run()
            except Exception as e:
                self.message(f"İndirme başlatılamadı: {e}", error=True)
        
        threading.Thread(target=worker, daemon=True).start()

    def clear_content_area(self):
        """İçerik alanını temizle."""
        for widget in self.content_area.winfo_children():
            widget.destroy()

    def show_home(self):
        """Ana sayfayı göster."""
        self.current_view = "home"
        self.clear_content_area()

        # Navigasyon butonlarını güncelle
        self.btnHome.configure(text_color="#ffffff", font=ctk.CTkFont(size=10, weight="bold"))
        self.btnTrending.configure(text_color="#cccccc", font=ctk.CTkFont(size=10))
        self.btnDownloads.configure(text_color="#cccccc", font=ctk.CTkFont(size=10))
        if hasattr(self, 'btnWatchlist'):
            self.btnWatchlist.configure(text_color="#cccccc", font=ctk.CTkFont(size=10))

        # Discord Rich Presence güncelle
        self.update_discord_presence("Ana sayfada", "TürkAnimu GUI")

        self.create_home_content()

    def show_trending(self):
        """Trend sayfası göster."""
        self.current_view = "trending"
        self.clear_content_area()

        # Navigasyon butonlarını güncelle
        self.btnHome.configure(text_color="#cccccc", font=ctk.CTkFont(size=10))
        self.btnTrending.configure(text_color="#ffffff", font=ctk.CTkFont(size=10, weight="bold"))
        self.btnDownloads.configure(text_color="#cccccc", font=ctk.CTkFont(size=10))
        if hasattr(self, 'btnWatchlist'):
            self.btnWatchlist.configure(text_color="#cccccc", font=ctk.CTkFont(size=10))

        # Discord Rich Presence güncelle
        self.update_discord_presence("Trend animelere bakıyor", "TürkAnimu GUI")

        # Başlık
        title_frame = ctk.CTkFrame(self.content_area, fg_color="transparent")
        title_frame.pack(fill="x", pady=(20, 20))

        back_btn = ctk.CTkButton(title_frame, text="← Ana Sayfa",
                               command=self.show_home,
                               fg_color="transparent", text_color="#ff6b6b",
                               font=ctk.CTkFont(size=14, weight="bold"))
        back_btn.pack(side="left")

        trending_title = ctk.CTkLabel(title_frame, text="🔥 Trend Animeler",
                    font=ctk.CTkFont(size=28, weight="bold"),
                    text_color="#ffffff")
        trending_title.pack(side="left", padx=30)

    # Trend grid (use non-scrollable grid; page itself scrolls)
        self.trending_full_grid = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self.trending_full_grid.pack(fill="both", expand=True)

        # Loading
        loading_label = ctk.CTkLabel(self.trending_full_grid, text="Trend animeler yükleniyor...",
                                   font=ctk.CTkFont(size=16),
                                   text_color="#888888")
        loading_label.pack(pady=50)

        # Trend animeleri yükle
        def load_worker():
            try:
                trending = anilist_client.get_trending_anime(page=1, per_page=50)
                self.after(0, lambda: self.display_full_trending(trending, loading_label))
            except Exception as e:
                error_msg = str(e)
                self.after(0, lambda: self.show_error(error_msg, loading_label))

        threading.Thread(target=load_worker, daemon=True).start()

    def show_downloads(self):
        """İndirilenler sayfası göster."""
        self.current_view = "downloads"
        self.clear_content_area()

        # Navigasyon butonlarını güncelle
        self.btnHome.configure(text_color="#cccccc", font=ctk.CTkFont(size=10))
        self.btnTrending.configure(text_color="#cccccc", font=ctk.CTkFont(size=10))
        self.btnDownloads.configure(text_color="#ffffff", font=ctk.CTkFont(size=10, weight="bold"))
        if hasattr(self, 'btnWatchlist'):
            self.btnWatchlist.configure(text_color="#cccccc", font=ctk.CTkFont(size=10))

        # Discord Rich Presence güncelle
        self.update_discord_presence("İndirilenlere bakıyor", "TürkAnimu GUI")

        # Başlık
        title_frame = ctk.CTkFrame(self.content_area, fg_color="transparent")
        title_frame.pack(fill="x", pady=(20, 20))

        back_btn = ctk.CTkButton(title_frame, text="← Ana Sayfa",
                               command=self.show_home,
                               fg_color="transparent", text_color="#ff6b6b",
                               font=ctk.CTkFont(size=14, weight="bold"))
        back_btn.pack(side="left")

        downloads_title = ctk.CTkLabel(title_frame, text="⬇️ İndirilenler",
                                     font=ctk.CTkFont(size=28, weight="bold"),
                                     text_color="#ffffff")
        downloads_title.pack(side="left", padx=30)

        # Yenile butonu
        refresh_btn = ctk.CTkButton(title_frame, text="🔄 Yenile",
                                  command=self.show_downloads,
                                  fg_color="#4ecdc4", hover_color="#45b7aa",
                                  width=100, height=35)
        refresh_btn.pack(side="right")

        # İndirilenler grid
        self.downloads_grid = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self.downloads_grid.pack(fill="both", expand=True)

        # Loading
        loading_label = ctk.CTkLabel(self.downloads_grid, text="İndirilenler yükleniyor...",
                                   font=ctk.CTkFont(size=16),
                                   text_color="#888888")
        loading_label.pack(pady=50)

        # İndirilen dosyaları yükle
        def load_worker():
            try:
                downloads = self.get_downloaded_files()
                self.after(0, lambda: self.display_downloads(downloads, loading_label))
            except Exception as e:
                error_msg = str(e)
                self.after(0, lambda: self.show_error(error_msg, loading_label))

        threading.Thread(target=load_worker, daemon=True).start()

    def get_downloaded_files(self):
        """İndirilen dosyaları tara."""
        import os
        from pathlib import Path

        downloads = []
        try:
            dosya = Dosyalar()
            indirilenler_dir = dosya.ayarlar.get("indirilenler", ".")

            # Önce mevcut indirilenler listesini ekle
            downloads.extend(self.downloaded_episodes)

            # Klasör taraması yap
            if not os.path.exists(indirilenler_dir):
                return downloads

            # Tüm video dosyalarını tara
            video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm']

            for root, dirs, files in os.walk(indirilenler_dir):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in video_extensions):
                        file_path = os.path.join(root, file)
                        file_size = os.path.getsize(file_path)
                        file_date = os.path.getmtime(file_path)

                        # Zaten listede var mı kontrol et
                        existing = False
                        for item in downloads:
                            if item.get('file_path') == file_path:
                                existing = True
                                break

                        if not existing:
                            # Anime adı ve bölüm numarasını çıkar
                            anime_name = os.path.basename(root)
                            episode_name = file

                            downloads.append({
                                'anime_name': anime_name,
                                'episode_name': episode_name,
                                'file_path': file_path,
                                'file_size': file_size,
                                'file_date': file_date
                            })

            # Tarihe göre sırala (en yeni önce)
            downloads.sort(key=lambda x: x['file_date'], reverse=True)

        except Exception as e:
            print(f"İndirilenler tarama hatası: {e}")

        return downloads

    def display_downloads(self, downloads, loading_label):
        """İndirilenleri göster."""
        loading_label.destroy()

        if not downloads:
            no_downloads_label = ctk.CTkLabel(self.downloads_grid,
                                            text="Henüz indirilen dosya bulunamadı.\nİndirilenler klasörünü ayarlar'dan kontrol edin.",
                                            font=ctk.CTkFont(size=16),
                                            text_color="#888888")
            no_downloads_label.pack(pady=50)
            return

        # İndirilenler listesi
        downloads_frame = ctk.CTkScrollableFrame(self.downloads_grid, fg_color="transparent")
        downloads_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        for download in downloads:
            # Dosya kartı
            file_frame = ctk.CTkFrame(downloads_frame, fg_color="#2a2a2a", corner_radius=10)
            file_frame.pack(fill="x", pady=5)

            # Sol taraf - Dosya bilgileri
            info_frame = ctk.CTkFrame(file_frame, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=15, pady=10)

            # Anime adı
            anime_label = ctk.CTkLabel(info_frame, text=download['anime_name'],
                                     font=ctk.CTkFont(size=14, weight="bold"),
                                     text_color="#ffffff")
            anime_label.pack(anchor="w")

            # Bölüm adı
            episode_label = ctk.CTkLabel(info_frame, text=download['episode_name'],
                                       font=ctk.CTkFont(size=12),
                                       text_color="#cccccc")
            episode_label.pack(anchor="w", pady=(2, 5))

            # Dosya boyutu ve tarih
            import time
            size_mb = download['file_size'] / (1024 * 1024)
            date_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(download['file_date']))

            details_label = ctk.CTkLabel(info_frame,
                                       text=f"{size_mb:.1f} MB • {date_str}",
                                       font=ctk.CTkFont(size=10),
                                       text_color="#888888")
            details_label.pack(anchor="w")

            # Sağ taraf - Aksiyon butonları
            actions_frame = ctk.CTkFrame(file_frame, fg_color="transparent")
            actions_frame.pack(side="right", padx=15, pady=10)

            # Oynat butonu
            play_btn = ctk.CTkButton(actions_frame, text="▶️ Oynat",
                                   command=lambda p=download['file_path']: self.play_local_file(p),
                                   fg_color="#4ecdc4", hover_color="#45b7aa",
                                   width=80, height=32)
            play_btn.pack(side="left", padx=(0, 5))

            # Klasörde göster butonu
            show_btn = ctk.CTkButton(actions_frame, text="📁 Göster",
                                   command=lambda p=download['file_path']: self.show_in_folder(p),
                                   fg_color="#666666", width=80, height=32)
            show_btn.pack(side="left")

    def play_local_file(self, file_path):
        """Yerel dosyayı oynat."""
        try:
            import subprocess
            import platform

            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", file_path])
            else:  # Linux
                subprocess.run(["xdg-open", file_path])

            self.message("Dosya açılıyor...", error=False)
        except Exception as e:
            self.message(f"Dosya açılırken hata: {e}", error=True)

    def update_downloaded_list(self, bolum, down_dir):
        """İndirilenler listesini güncelle."""
        try:
            import os
            from pathlib import Path

            # İndirilen dosya yolunu oluştur
            anime_slug = bolum.anime.slug if bolum.anime else ""
            file_path = os.path.join(down_dir, anime_slug, bolum.slug + ".mp4")

            # Dosya mevcut mu kontrol et
            if os.path.exists(file_path):
                # İndirilenler listesine ekle
                # Zaten listede var mı kontrol et
                existing = False
                for item in self.downloaded_episodes:
                    if item.get('file_path') == file_path:
                        existing = True
                        break

                if not existing:
                    self.downloaded_episodes.append({
                        'anime_name': bolum.anime.title if bolum.anime else "Bilinmeyen Anime",
                        'episode_name': bolum.title,
                        'file_path': file_path,
                        'file_size': os.path.getsize(file_path),
                        'file_date': os.path.getmtime(file_path)
                    })

                    # Listeyi tarihe göre sırala
                    self.downloaded_episodes.sort(key=lambda x: x['file_date'], reverse=True)

        except Exception as e:
            print(f"İndirilenler listesi güncelleme hatası: {e}")

    def show_in_folder(self, file_path):
        """Dosyanın bulunduğu klasörü göster."""
        try:
            import subprocess
            import platform

            folder_path = os.path.dirname(file_path)

            if platform.system() == "Windows":
                subprocess.run(["explorer", "/select,", file_path])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", "-R", file_path])
            else:  # Linux
                subprocess.run(["xdg-open", folder_path])

        except Exception as e:
            self.message(f"Klasör açılırken hata: {e}", error=True)

    def display_full_trending(self, anime_list, loading_label):
        """Tam trend listesini göster."""
        loading_label.destroy()

        row = 0
        col = 0
        max_cols = 6

        for anime in anime_list:
            if col >= max_cols:
                col = 0
                row += 1

            self.create_anime_card(self.trending_full_grid, anime, row, col, max_cols)
            col += 1

    def show_watchlist(self):
        """İzleme listesi göster."""
        if not anilist_client.access_token:
            self.message("AniList girişi gerekli", error=True)
            return

        self.current_view = "watchlist"
        self.clear_content_area()

        # Navigasyon butonlarını güncelle
        self.btnHome.configure(text_color="#cccccc", font=ctk.CTkFont(size=10))
        self.btnTrending.configure(text_color="#cccccc", font=ctk.CTkFont(size=10))
        self.btnDownloads.configure(text_color="#cccccc", font=ctk.CTkFont(size=10))
        if hasattr(self, 'btnWatchlist'):
            self.btnWatchlist.configure(text_color="#ffffff", font=ctk.CTkFont(size=10, weight="bold"))

        # Başlık
        title_frame = ctk.CTkFrame(self.content_area, fg_color="transparent")
        title_frame.pack(fill="x", pady=(20, 20))

        back_btn = ctk.CTkButton(title_frame, text="← Ana Sayfa",
                               command=self.show_home,
                               fg_color="transparent", text_color="#ff6b6b",
                               font=ctk.CTkFont(size=14, weight="bold"))
        back_btn.pack(side="left")

        watchlist_title = ctk.CTkLabel(title_frame, text="📋 İzleme Listem",
                                     font=ctk.CTkFont(size=28, weight="bold"),
                                     text_color="#ffffff")
        watchlist_title.pack(side="left", padx=30)

        # Liste tipi seçici
        list_type_frame = ctk.CTkFrame(title_frame, fg_color="transparent")
        list_type_frame.pack(side="right")

        self.cmbListType = ctk.CTkComboBox(list_type_frame,
                                         values=["CURRENT", "PLANNING", "COMPLETED", "DROPPED", "PAUSED"],
                                         command=self.on_watchlist_type_change,
                                         width=120, height=35)
        self.cmbListType.pack()
        self.cmbListType.set("CURRENT")

        # Watchlist grid (non-scrollable; page scrolls)
        self.watchlist_grid = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self.watchlist_grid.pack(fill="both", expand=True)

        # Loading
        loading_label = ctk.CTkLabel(self.watchlist_grid, text="İzleme listesi yükleniyor...",
                                   font=ctk.CTkFont(size=16),
                                   text_color="#888888")
        loading_label.pack(pady=50)

        # Watchlist yükle
        self.load_watchlist(loading_label)

    def load_watchlist(self, loading_label):
        """İzleme listesi yükle."""
        def load_worker():
            try:
                if not self.anilist_user:
                    raise Exception("Kullanıcı bilgileri bulunamadı")

                user_id = self.anilist_user.get('id')
                if not user_id:
                    raise Exception("Kullanıcı ID bulunamadı")

                list_type = self.cmbListType.get() if hasattr(self, 'cmbListType') else "CURRENT"

                results = anilist_client.get_user_anime_list(user_id, list_type)

                # Anime listesini çıkar
                anime_list = []
                for list_item in results:
                    for entry in list_item.get('entries', []):
                        anime_data = entry.get('media', {})
                        anime_data['user_progress'] = entry.get('progress', 0)
                        anime_data['user_score'] = entry.get('score', 0)
                        anime_data['user_status'] = entry.get('status', 'CURRENT')
                        anime_list.append(anime_data)

                self.after(0, lambda: self.display_watchlist(anime_list, loading_label))
            except Exception as e:
                error_msg = str(e)
                self.after(0, lambda: self.show_error(error_msg, loading_label))

        threading.Thread(target=load_worker, daemon=True).start()

    def display_watchlist(self, anime_list, loading_label):
        """İzleme listesini göster."""
        loading_label.destroy()

        if not anime_list:
            empty_label = ctk.CTkLabel(self.watchlist_grid,
                                     text="Bu kategoride anime bulunamadı",
                                     font=ctk.CTkFont(size=16),
                                     text_color="#888888")
            empty_label.pack(pady=50)
            return

        row = 0
        col = 0
        max_cols = 7

        for anime in anime_list:
            if col >= max_cols:
                col = 0
                row += 1

            self.create_watchlist_card(self.watchlist_grid, anime, row, col, max_cols)
            col += 1

    def create_watchlist_card(self, parent, anime_data, row, col, max_cols):
        """İzleme listesi kartı oluştur."""
        card_frame = ctk.CTkFrame(parent, fg_color="#2a2a2a", width=180, height=320)
        card_frame.grid(row=row, column=col, padx=4, pady=4, sticky="nw")
        card_frame.pack_propagate(False)

        # Hover efekti
        def on_enter(e):
            card_frame.configure(fg_color="#3a3a3a")

        def on_leave(e):
            card_frame.configure(fg_color="#2a2a2a")

        card_frame.bind("<Enter>", on_enter)
        card_frame.bind("<Leave>", on_leave)

        # Kapak görseli
        cover_frame = ctk.CTkFrame(card_frame, fg_color="#1a1a1a", width=160, height=200)
        cover_frame.pack(pady=(10, 0))
        cover_frame.pack_propagate(False)

        cover_label = ctk.CTkLabel(cover_frame, text="", font=ctk.CTkFont(size=60))
        cover_label.pack(expand=True)

        # Kapak görselini yükle
        cover_url = anime_data.get('coverImage', {}).get('large')
        if cover_url:
            self.load_anilist_thumbnail(cover_url, cover_label, 140, 180)

        # Başlık
        title_text = anime_data.get('title', {}).get('romaji', 'Unknown')
        if len(title_text) > 18:
            title_text = title_text[:15] + "..."

        title_label = ctk.CTkLabel(card_frame, text=title_text,
                                 font=ctk.CTkFont(size=11, weight="bold"),
                                 text_color="#ffffff", wraplength=160)
        title_label.pack(pady=(8, 0))

        # Progress
        user_progress = anime_data.get('user_progress', 0)
        total_episodes = anime_data.get('episodes')

        if user_progress is not None and total_episodes:
            progress_text = f"İzlenen: {user_progress}/{total_episodes}"
            progress_label = ctk.CTkLabel(card_frame, text=progress_text,
                                        font=ctk.CTkFont(size=10),
                                        text_color="#4ecdc4")
            progress_label.pack(pady=(2, 0))

            # Progress bar
            progress_value = (user_progress / total_episodes) * 100
            progress_bar = ctk.CTkProgressBar(card_frame, width=140, height=6)
            progress_bar.pack(pady=(2, 0))
            progress_bar.set(progress_value / 100)

        # Skor
        user_score = anime_data.get('user_score', 0)
        if user_score and user_score > 0:
            score_label = ctk.CTkLabel(card_frame, text=f"⭐ {user_score}/100",
                                     font=ctk.CTkFont(size=10),
                                     text_color="#ffd93d")
            score_label.pack(pady=(2, 0))

        # Status
        user_status = anime_data.get('user_status', 'CURRENT')
        status_colors = {
            "CURRENT": "#4CAF50",
            "PLANNING": "#2196F3",
            "COMPLETED": "#9C27B0",
            "DROPPED": "#F44336",
            "PAUSED": "#FF9800"
        }
        status_color = status_colors.get(user_status, "#666666")
        status_label = ctk.CTkLabel(card_frame, text=user_status,
                                  font=ctk.CTkFont(size=9),
                                  text_color=status_color)
        status_label.pack(pady=(4, 8))

        # Tıkla eventi
        def on_click():
            self.show_anime_details(anime_data)

        card_frame.bind("<Button-1>", lambda e: on_click())

    def message(self, text, error=False):
        """Durum mesajı göster."""
        if hasattr(self, 'status_label'):
            color = "#ff6b6b" if error else "#cccccc"
            self.status_label.configure(text=text, text_color=color)
        else:
            print(f"Message: {text}")

    def on_watchlist_type_change(self, list_type):
        """İzleme listesi tipi değişti."""
        if hasattr(self, 'watchlist_grid'):
            # Mevcut içeriği temizle
            for widget in self.watchlist_grid.winfo_children():
                widget.destroy()

            # Loading
            loading_label = ctk.CTkLabel(self.watchlist_grid, text="Yükleniyor...",
                                       font=ctk.CTkFont(size=16),
                                       text_color="#888888")
            loading_label.pack(pady=50)

            # Yeni listeyi yükle
            self.load_watchlist(loading_label)

    def show_trending_error(self, error_msg):
        """Trend yükleme hatası göster."""
        if hasattr(self, 'loading_label'):
            self.loading_label.configure(text=f"Hata: {error_msg}", text_color="#ff6b6b")

    def show_error(self, error_msg, widget_to_replace):
        """Hata mesajı göster."""
        widget_to_replace.configure(text=f"Hata: {error_msg}", text_color="#ff6b6b")

    def search_anime_locally(self, title):
        """Anime'yi yerel kaynaklarda ara."""
        # Yeni UI'da arama yapmak için searchEntry'yi kullan
        if hasattr(self, 'searchEntry'):
            self.searchEntry.delete(0, "end")
            self.searchEntry.insert(0, title)
            self.on_search()
        else:
            self.message("Arama özelliği mevcut değil", error=True)

    def on_search(self):
        """Yeni UI için arama yap."""
        if not hasattr(self, 'searchEntry'):
            self.message("Arama özelliği mevcut değil", error=True)
            return

        query = self.searchEntry.get().strip()
        if not query:
            self.message("Arama terimi girin", error=True)
            return

        # Discord Rich Presence güncelle
        self.update_discord_presence(f"'{query}' arıyor", "TürkAnimu GUI")

        # AniList'te ara
        self.message("AniList'te aranıyor…")

        def search_worker():
            try:
                results = anilist_client.search_anime(query)
                self.after(0, lambda: self.display_anilist_search_results(results, f"AniList Arama: {query}"))
            except Exception as e:
                self.after(0, lambda: self.message(f"AniList arama hatası: {e}", error=True))

        threading.Thread(target=search_worker, daemon=True).start()

    # --- AniList Methods ---
    def on_anilist_login(self):
        """AniList OAuth login."""
        try:
            # Start local auth server first (avoid race where browser redirects before server ready)
            if not self.anilist_auth_server:
                self.anilist_auth_server = AniListAuthServer(anilist_client)
                # UI'yi güncellemek için success callback bağla
                try:
                    # Başarılı girişte kullanıcı bilgisini UI'ye yansıt
                    def _on_success():
                        # UI güncelle
                        self.after(0, self.check_anilist_auth_status)
                        # Sunucu referansını temizle
                        self.anilist_auth_server = None
                    self.anilist_auth_server.register_on_success(_on_success)
                except Exception:
                    pass
                threading.Thread(target=self.anilist_auth_server.start_server, daemon=True).start()

            # Open browser for OAuth (use authorization code flow: response_type=code)
            auth_url = anilist_client.get_auth_url(response_type="code")
            webbrowser.open(auth_url)

            self.message("Tarayıcıda AniList girişini tamamlayın")
        except Exception as e:
            self.message(f"AniList giriş hatası: {e}", error=True)
            self.lblAniListUser.configure(text="Giriş yapılmamış")

    def on_anilist_logout(self):
        """AniList logout."""
        try:
            anilist_client.clear_tokens()
        except Exception:
            anilist_client.access_token = None
            anilist_client.refresh_token = None
        anilist_client.user_data = None
        self.anilist_user = None
        self.lblAniListUser.configure(text="Giriş yapılmamış")
        self.message("AniList oturumu kapatıldı")

    def on_anilist_search(self):
        """AniList'te ara."""
        # Bu method artık kullanılmıyor, on_search kullanılıyor
        pass

    def on_anilist_trending(self):
        """Get trending anime from AniList."""
        self.message("Trend animeler yükleniyor…")

        def trending_worker():
            try:
                results = anilist_client.get_trending_anime()
                self.after(0, lambda: self.display_anilist_results(results, "AniList Trendler"))
            except Exception as e:
                self.after(0, lambda: self.message(f"Trend yükleme hatası: {e}", error=True))

        threading.Thread(target=trending_worker, daemon=True).start()

    def on_anilist_watchlist(self):
        """Load user's AniList watchlist."""
        if not anilist_client.access_token:
            self.message("AniList girişi gerekli", error=True)
            return

        if not self.anilist_user:
            self.message("Kullanıcı bilgileri yüklenemedi", error=True)
            return

        self.message("İzleme listesi yükleniyor…")

        def watchlist_worker():
            try:
                if not self.anilist_user:
                    raise Exception("Kullanıcı bilgileri bulunamadı")

                user_id = self.anilist_user.get('id')
                if not user_id:
                    raise Exception("Kullanıcı ID bulunamadı")

                list_type = self.anilist_current_list_type
                results = anilist_client.get_user_anime_list(user_id, list_type)

                # Extract anime from lists
                anime_list = []
                for list_item in results:
                    for entry in list_item.get('entries', []):
                        anime_data = entry.get('media', {})
                        anime_data['user_progress'] = entry.get('progress', 0)
                        anime_data['user_score'] = entry.get('score', 0)
                        anime_data['user_status'] = entry.get('status', 'CURRENT')
                        anime_list.append(anime_data)

                self.after(0, lambda: self.display_anilist_results(anime_list, f"AniList {list_type} Listesi"))
            except Exception as e:
                self.after(0, lambda: self.message(f"İzleme listesi hatası: {e}", error=True))

        threading.Thread(target=watchlist_worker, daemon=True).start()

    def on_anilist_sync(self):
        """Sync progress with AniList."""
        if not anilist_client.access_token:
            self.message("AniList girişi gerekli", error=True)
            return

        self.message("AniList ile senkronize ediliyor…")

        def sync_worker():
            try:
                self.sync_progress_with_anilist()
                self.after(0, lambda: self.message("Senkronizasyon tamamlandı"))
            except Exception as e:
                self.after(0, lambda: self.message(f"Senkronizasyon hatası: {e}", error=True))

        threading.Thread(target=sync_worker, daemon=True).start()

    def on_anilist_list_type_change(self, list_type: str):
        """Handle list type change."""
        self.anilist_current_list_type = list_type
        if anilist_client.access_token and self.anilist_user:
            self.on_anilist_watchlist()

    def display_anilist_results(self, results: List[Dict], title: str):
        """AniList arama sonuçlarını göster."""
        # İçerik alanını temizle
        self.clear_content_area()

        if not results:
            no_results_label = ctk.CTkLabel(self.content_area, text="Sonuç bulunamadı",
                                          font=ctk.CTkFont(size=16),
                                          text_color="#888888")
            no_results_label.pack(pady=50)
            self.message("Sonuç bulunamadı")
            return

        # Başlık
        title_frame = ctk.CTkFrame(self.content_area, fg_color="transparent")
        title_frame.pack(fill="both", pady=(20, 20))

        back_btn = ctk.CTkButton(title_frame, text="← Ana Sayfa",
                               command=self.show_home,
                               fg_color="transparent", text_color="#ff6b6b",
                               font=ctk.CTkFont(size=14, weight="bold"))
        back_btn.pack(side="left")

        search_title = ctk.CTkLabel(title_frame, text=title,
                                  font=ctk.CTkFont(size=28, weight="bold"),
                                  text_color="#ffffff")
        search_title.pack(side="left", padx=30)

        # Sonuçlar grid'i
        results_grid = ctk.CTkFrame(self.content_area, fg_color="transparent", height=600)
        results_grid.pack(fill="both", expand=True)

        row = 0
        col = 0
        max_cols = 6

        for anime in results[:30]:  # Limit to 30 results
            if col >= max_cols:
                col = 0
                row += 6

            self.create_anime_card(results_grid, anime, row, col, max_cols)
            col += 1

        self.message(f"{len(results)} sonuç bulundu")

    def display_anilist_search_results(self, results: List[Dict], title: str):
        """AniList arama sonuçlarını göster."""
        self.display_anilist_results(results, title)

    def add_anilist_to_library(self, anime_data: Dict):
        """AniList anime'yi yerel arama için kullan."""
        try:
            title = anime_data.get('title', {}).get('romaji', 'Unknown')

            # Yeni UI'da arama yapmak için searchEntry'yi kullan
            if hasattr(self, 'searchEntry'):
                self.searchEntry.delete(0, "end")
                self.searchEntry.insert(0, title)
                self.on_search()
                self.message(f"'{title}' için yerel arama başlatıldı")
            else:
                self.message("Arama özelliği mevcut değil", error=True)
        except Exception as e:
            self.message(f"Anime ekleme hatası: {e}", error=True)

    def update_anilist_progress(self, anime_data: Dict):
        """AniList'e izleme ilerlemesini kaydet."""
        try:
            anime_id = anime_data.get('id')
            if not anime_id:
                raise Exception("Anime ID bulunamadı")

            current_progress = anime_data.get('user_progress', 0)
            total_episodes = anime_data.get('episodes', 0)

            # Simple progress update dialog
            from tkinter import simpledialog
            progress_input = simpledialog.askstring(
                f"Progress Güncelle - {anime_data.get('title', {}).get('romaji', 'Unknown')}",
                f"İzlenen bölüm sayısı (0-{total_episodes}):",
                initialvalue=str(current_progress)
            )

            if progress_input:
                try:
                    new_progress = int(progress_input)
                    if 0 <= new_progress <= total_episodes:
                        success = anilist_client.update_anime_progress(anime_id, new_progress)
                        if success:
                            self.message(f"Progress güncellendi: {new_progress}/{total_episodes}")
                            # Refresh watchlist
                            self.on_anilist_watchlist()
                        else:
                            self.message("Progress güncelleme başarısız", error=True)
                    else:
                        self.message(f"Geçersiz progress: 0-{total_episodes} arası olmalı", error=True)
                except ValueError:
                    self.message("Geçersiz sayı", error=True)

        except Exception as e:
            self.message(f"Progress güncelleme hatası: {e}", error=True)

    def load_anilist_thumbnail(self, url: str, label: ctk.CTkLabel, width: int = 120, height: int = 160):
        """Load and display AniList thumbnail asynchronously."""
        if not url:
            return

        # Check cache first
        if url in self.anilist_image_cache:
            try:
                label.configure(image=self.anilist_image_cache[url])
                return
            except:
                pass

        def load_image():
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                # Open image with PIL
                image = Image.open(io.BytesIO(response.content))

                # Resize to fit
                image.thumbnail((width, height), Image.Resampling.LANCZOS)

                # Convert to CTkImage
                ctk_image = ctk.CTkImage(image, size=(width, height))

                # Cache the image
                self.anilist_image_cache[url] = ctk_image

                # Update label in main thread
                self.after(0, lambda: label.configure(image=ctk_image))

            except Exception as e:
                print(f"Thumbnail load error: {e}")
                # Fallback to text (fix: set image=None to avoid string warning)
                self.after(0, lambda: label.configure(text="[Kapak]", image=None))

        threading.Thread(target=load_image, daemon=True).start()

    def load_avatar(self, avatar_url, username):
        """Load and display user avatar."""
        try:
            # Avatar'ı indir
            response = requests.get(avatar_url, timeout=10)
            response.raise_for_status()

            # PIL ile image'ı aç
            image_data = Image.open(io.BytesIO(response.content))

            # 32x32 boyutuna yeniden boyutlandır
            image_data = image_data.resize((32, 32), Image.Resampling.LANCZOS)

            # CTkImage oluştur
            ctk_image = ctk.CTkImage(image_data, size=(32, 32))

            # UI thread'de güncelle
            self.after(0, lambda: self.update_avatar_display(ctk_image, username))

        except Exception as e:
            print(f"Avatar load error: {e}")
            # Hata durumunda text göster
            self.after(0, lambda: self.update_avatar_display(None, username))

    def update_avatar_display(self, avatar_image, username):
        """Update avatar display in UI thread."""
        if avatar_image:
            self.avatarLabel.configure(image=avatar_image, text="")
            self.lblAniListUser.configure(text=f"{username}")
        else:
            self.avatarLabel.configure(image="", text="")
            self.lblAniListUser.configure(text=f"{username}")

    def check_anilist_auth_status(self):
        """Check and update AniList authentication status."""
        try:
            if anilist_client.access_token:
                user = anilist_client.get_current_user()
                if user:
                    self.anilist_user = user
                    username = user.get('name', 'Unknown')

                    # Avatar URL'sini al
                    avatar_url = user.get('avatar', {}).get('large')
                    if avatar_url:
                        # Avatar'ı yükle ve göster
                        threading.Thread(target=self.load_avatar, args=(avatar_url, username), daemon=True).start()
                    else:
                        # Avatar yoksa text göster
                        self.lblAniListUser.configure(text=f"{username}")
                        self.avatarLabel.configure(image="", text="")

                    # Listem butonunu göster
                    if hasattr(self, 'btnWatchlist'):
                        self.btnWatchlist.pack(side="left", padx=1)

                else:
                    self.lblAniListUser.configure(text="Giriş yapılmamış")
                    self.avatarLabel.configure(image="", text="")
                    # Listem butonunu gizle
                    if hasattr(self, 'btnWatchlist'):
                        self.btnWatchlist.pack_forget()
            else:
                self.lblAniListUser.configure(text="Giriş yapılmamış")
                self.avatarLabel.configure(image="", text="")
                # Listem butonunu gizle
                if hasattr(self, 'btnWatchlist'):
                    self.btnWatchlist.pack_forget()
        except Exception as e:
            print(f"AniList auth check error: {e}")
            self.lblAniListUser.configure(text="Giriş yapılmamış")
            self.avatarLabel.configure(image="", text="")
            # Hata durumunda da Listem butonunu gizle
            if hasattr(self, 'btnWatchlist'):
                self.btnWatchlist.pack_forget()

    # --- Local Progress Tracking Methods ---
    def load_local_progress(self):
        """Load local anime progress from storage."""
        try:
            import appdirs
            data_dir = appdirs.user_data_dir("TurkAnime", "Barkeser")
            os.makedirs(data_dir, exist_ok=True)
            progress_file = os.path.join(data_dir, "anime_progress.json")
            if os.path.exists(progress_file):
                with open(progress_file, 'r', encoding='utf-8') as f:
                    self.local_anime_progress = json.load(f)
            else:
                self.local_anime_progress = {}
        except Exception as e:
            print(f"Local progress load error: {e}")
            self.local_anime_progress = {}

    def save_local_progress(self):
        """Save local anime progress to storage."""
        try:
            import appdirs
            data_dir = appdirs.user_data_dir("TurkAnime", "Barkeser")
            os.makedirs(data_dir, exist_ok=True)
            progress_file = os.path.join(data_dir, "anime_progress.json")
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.local_anime_progress, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Local progress save error: {e}")

    def update_local_progress(self, anime_title: str, progress: int, total_episodes: Optional[int] = None):
        """Update local progress for an anime."""
        self.local_anime_progress[anime_title] = {
            'progress': progress,
            'total_episodes': total_episodes,
            'last_updated': time.time()
        }
        self.save_local_progress()

    def get_local_progress(self, anime_title: str) -> Dict:
        """Get local progress for an anime."""
        return self.local_anime_progress.get(anime_title, {})

    def on_play_selected(self):
        """Seçili bölümü veya ilk bölümü oynat."""
        # Detay sayfasında seçili bölüm varsa onu oynat
        if getattr(self, 'episodes_vars', None):
            for var, obj in self.episodes_vars:
                if var.get():
                    self._play_episode(obj)
                    return
            # Seçili yoksa ilk bölümü oynat
            if getattr(self, 'episodes_objs', None):
                self._play_episode(self.episodes_objs[0])
                return
        self.message("Önce bir anime açıp bölüm seçin", error=True)

    def on_download_selected(self):
        """Seçili bölümleri indir."""
        if getattr(self, 'episodes_vars', None):
            selected = [obj for var, obj in self.episodes_vars if var.get()]
            if not selected and getattr(self, 'episodes_objs', None):
                # Seçim yoksa ilk bölümü indir
                selected = [self.episodes_objs[0]]
            if selected:
                def worker():
                    try:
                        dw = DownloadWorker(selected)
                        dw.signals.connect_progress(lambda msg: self.status_label.configure(text=msg))
                        dw.signals.connect_success(lambda: self.message("İndirme tamamlandı!"))
                        dw.signals.connect_error(lambda msg: self.message(f"İndirme hatası: {msg}", error=True))
                        dw.run()
                    except Exception as e:
                        self.message(f"İndirme başlatılamadı: {e}", error=True)
                threading.Thread(target=worker, daemon=True).start()
                return
        self.message("Önce bir anime açıp bölüm seçin", error=True)

    def load_episodes_and_play(self, anime: Anime):
        """Anime bölümlerini yükle ve oynat."""
        def load_worker():
            try:
                self.status_label.configure(text=f"'{anime.title}' bölümleri yükleniyor...")
                episodes = anime.bolumler

                if episodes:
                    # İlk bölümü oynat
                    first_episode = episodes[0]
                    self.status_label.configure(text=f"'{first_episode.title}' oynatılıyor...")

                    # Video arama worker'ı başlat
                    video_worker = VideoFindWorker(first_episode)
                    video_worker.signals.connect_found(self.play_video)
                    video_worker.signals.connect_error(lambda msg: self.message(f"Hata: {msg}"))

                    threading.Thread(target=video_worker.run, daemon=True).start()
                else:
                    self.message("Bölüm bulunamadı.")

            except Exception as e:
                self.message(f"Bölüm yükleme hatası: {str(e)}")
            finally:
                self.status_label.configure(text="TürkAnimu hazır")

        threading.Thread(target=load_worker, daemon=True).start()

    def load_episodes_and_download(self, anime: Anime):
        """Anime bölümlerini yükle ve indir."""
        def load_worker():
            try:
                self.status_label.configure(text=f"'{anime.title}' bölümleri yükleniyor...")
                episodes = anime.bolumler

                if episodes:
                    self.status_label.configure(text=f"{len(episodes)} bölüm indiriliyor...")

                    # Download worker başlat
                    download_worker = DownloadWorker(episodes)
                    download_worker.signals.connect_progress(lambda msg: self.status_label.configure(text=msg))
                    download_worker.signals.connect_success(lambda: self.message("İndirme tamamlandı!"))
                    download_worker.signals.connect_error(lambda msg: self.message(f"İndirme hatası: {msg}"))

                    threading.Thread(target=download_worker.run, daemon=True).start()
                else:
                    self.message("Bölüm bulunamadı.")

            except Exception as e:
                self.message(f"Bölüm yükleme hatası: {str(e)}")
            finally:
                self.status_label.configure(text="TürkAnimu hazır")

        threading.Thread(target=load_worker, daemon=True).start()

    def play_video(self, video_data):
        """Video'yu oynat."""
        try:
            # Bölüm objesini al ve Discord Rich Presence güncelle
            episode_obj = video_data.get('bolum') if hasattr(video_data, 'get') else getattr(video_data, 'bolum', None)
            anime_image = None
            
            if episode_obj and episode_obj.anime:
                anime_title = episode_obj.anime.title
                episode_title = episode_obj.title
                
                # Discord Rich Presence güncelle - AniList button'u ile
                anime_data = self.selected_anime
                anilist_id = anime_data.get('id') if anime_data else None
                
                buttons = [
                    {
                        "label": "Uygulamayı Edin",
                        "url": "https://github.com/barkeser2002/turkanime-indirici/releases"
                    }
                ]
                
                if anilist_id:
                    buttons.append({
                        "label": "AniList'te Gör",
                        "url": f"https://anilist.co/anime/{anilist_id}"
                    })
                
                self.update_discord_presence_anime(anime_title, f"Bölüm: {episode_title}", anime_image, buttons)

            # Video player ile oynat (mpv, vlc vb.)
            import subprocess
            import platform

            video_url = video_data.get('url')
            if video_url:
                if platform.system() == "Windows":
                    # Windows için mpv veya vlc kullan
                    try:
                        subprocess.run(["mpv", video_url], check=True)
                    except FileNotFoundError:
                        try:
                            subprocess.run(["vlc", video_url], check=True)
                        except FileNotFoundError:
                            self.message("Video oynatıcı bulunamadı. mpv veya vlc yükleyin.")
                else:
                    # Linux/Mac için
                    try:
                        subprocess.run(["mpv", video_url], check=True)
                    except FileNotFoundError:
                        self.message("mpv bulunamadı. Lütfen yükleyin.")

                self.message("Video oynatma tamamlandı.")
                # İzleme ilerlemesi dialog'u aç
                self.show_progress_dialog(video_data)
            else:
                self.message("Video URL bulunamadı.")

        except Exception as e:
            self.message(f"Video oynatma hatası: {str(e)}")

    def show_progress_dialog(self, video_data):
        """İzleme ilerlemesi dialog'u göster."""
        try:
            # Bölüm objesini al
            episode_obj = video_data.get('bolum') if hasattr(video_data, 'get') else getattr(video_data, 'bolum', None)
            if not episode_obj:
                return

            # Anime bilgilerini al
            anime_title = episode_obj.anime.title if episode_obj.anime else "Bilinmeyen Anime"
            episode_title = episode_obj.title

            # Dialog oluştur
            dialog = ctk.CTkToplevel(self)
            dialog.title("İzleme İlerlemesi")
            dialog.geometry("400x250")
            dialog.resizable(False, False)

            # Dialog'u modal yap
            dialog.transient(self)
            dialog.grab_set()

            # Başlık
            title_label = ctk.CTkLabel(dialog, text="İzleme İlerlemesi Kaydet",
                                     font=ctk.CTkFont(size=16, weight="bold"))
            title_label.pack(pady=(20, 10))

            # Anime bilgisi
            info_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            info_frame.pack(fill="x", padx=20, pady=(0, 10))

            anime_info = ctk.CTkLabel(info_frame, text=f"Anime: {anime_title}",
                                    font=ctk.CTkFont(size=12))
            anime_info.pack(anchor="w")

            episode_info = ctk.CTkLabel(info_frame, text=f"Bölüm: {episode_title}",
                                      font=ctk.CTkFont(size=12))
            episode_info.pack(anchor="w")

            # Bölüm sayısı girişi
            input_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            input_frame.pack(fill="x", padx=20, pady=(10, 20))

            input_label = ctk.CTkLabel(input_frame, text="Kaçıncı bölümü tamamladınız?",
                                     font=ctk.CTkFont(size=12))
            input_label.pack(anchor="w", pady=(0, 5))

            episode_entry = ctk.CTkEntry(input_frame, placeholder_text="örn: 5")
            episode_entry.pack(fill="x")

            # Butonlar
            button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            button_frame.pack(fill="x", padx=20, pady=(0, 20))

            def save_progress():
                try:
                    episode_num = int(episode_entry.get().strip())
                    anime_id = self.selected_anime.get('id') if self.selected_anime else None
                    if not anime_id:
                        self.message("Anime ID bulunamadı", error=True)
                        return

                    # total_episodes her iki dalda da kullanılacağı için önce tanımla
                    total_episodes = self.selected_anime.get('episodes') if self.selected_anime else None

                    if episode_num > 0:
                        # normalize variable name used below
                        new_progress = episode_num
                        success = anilist_client.update_anime_progress(anime_id, new_progress)
                        if success:
                            self.message(f"Progress güncellendi: {new_progress}/{total_episodes}")
                            # Refresh watchlist
                            self.on_anilist_watchlist()
                        else:
                            self.message("Progress güncelleme başarısız", error=True)
                    else:
                        self.message(f"Geçersiz progress: 0-{total_episodes} arası olmalı", error=True)
                except ValueError:
                    self.message("Geçersiz sayı", error=True)

            def skip():
                dialog.destroy()

            save_btn = ctk.CTkButton(button_frame, text="Kaydet", command=save_progress,
                                   fg_color="#4ecdc4", hover_color="#45b7aa", width=100)
            save_btn.pack(side="left", padx=(0, 10))

            skip_btn = ctk.CTkButton(button_frame, text="Atla", command=skip,
                                   fg_color="#666666", width=100)
            skip_btn.pack(side="left")

            # Enter tuşu ile kaydet
            def on_enter(event):
                save_progress()
            episode_entry.bind("<Return>", on_enter)

            # Focus ayarla
            episode_entry.focus()

        except Exception as e:
            print(f"Progress dialog hatası: {e}")

    def save_anilist_progress(self, episode_obj, episode_num):
        """AniList'e izleme ilerlemesini kaydet."""
        try:
            if not anilist_client.access_token:
                self.message("AniList girişi gerekli", error=True)
                return

            # Anime ID'sini bul
            anime_title = episode_obj.anime.title if episode_obj.anime else ""
            if not anime_title:
                return

            # AniList'te anime ara
            search_results = anilist_client.search_anime(anime_title)
            if not search_results:
                self.message("Anime AniList'te bulunamadı", error=True)
                return

            # İlk sonucu al
            anime_data = search_results[0]
            anime_id = anime_data.get('id')

            if anime_id:
                # İlerlemesi güncelle
                success = anilist_client.update_anime_progress(anime_id, episode_num)
                if success:
                    self.message(f"AniList ilerlemesi güncellendi: Bölüm {episode_num}")
                    # Senkronizasyonu güncelle
                    self.sync_progress_with_anilist()
                else:
                    self.message("AniList güncelleme başarısız", error=True)

        except Exception as e:
            self.message(f"AniList güncelleme hatası: {e}", error=True)

    def sync_progress_with_anilist(self):
        """Sync local progress with AniList."""
        if not anilist_client.access_token or not self.anilist_user:
            return

        try:
            user_id = self.anilist_user.get('id')
            if not user_id:
                return

            # Get user's current anime list
            current_list = anilist_client.get_user_anime_list(user_id, "CURRENT")

            # Update local progress with AniList data
            for list_item in current_list:
                for entry in list_item.get('entries', []):
                    anime = entry.get('media', {})
                    title = anime.get('title', {}).get('romaji', 'Unknown')
                    progress = entry.get('progress', 0)
                    total_episodes = anime.get('episodes')

                    self.update_local_progress(title, progress, total_episodes)

            self.message("AniList ile senkronize edildi")
        except Exception as e:
            print(f"AniList sync error: {e}")

    def on_source_change(self, source):
        """Kaynak değiştiğinde çağrılır."""
        self.selected_source = source
        self.message(f"Kaynak {source} olarak ayarlandı")
        
        # Eğer anime detayları gösteriliyorsa bölümleri yeniden yükle
        if hasattr(self, 'selected_anime') and self.selected_anime:
            self.show_anime_details(self.selected_anime)

    def load_more_episodes(self):
        """Daha fazla bölüm yükle."""
        if self.is_loading_episodes or self.episodes_loaded >= len(self.all_episodes):
            return
        
        self.is_loading_episodes = True
        
        # Bu sayfada yüklenecek bölüm sayısı
        start_idx = self.episodes_loaded
        end_idx = min(start_idx + self.episodes_per_page, len(self.all_episodes))
        
        # Bölümleri yükle
        for i in range(start_idx, end_idx):
            episode = self.all_episodes[i]
            row = ctk.CTkFrame(self.episodes_list, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=4)

            var = ctk.BooleanVar(value=False)
            chk = ctk.CTkCheckBox(row, text=f"{i+1:02d} - {episode['title']}", variable=var)
            chk.pack(side="left")

            # Sağ aksiyonlar
            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.pack(side="right")
            
            btnPlay = ctk.CTkButton(actions, text="▶️", width=40, height=32,
                                  command=lambda obj=episode['obj']: self._play_episode(obj))
            btnPlay.pack(side="left", padx=(0, 5))
            
            btnDl = ctk.CTkButton(actions, text="⬇️", width=40, height=32,
                                command=lambda obj=episode['obj']: self._download_episode(obj))
            btnDl.pack(side="left")
            
            self.episodes_vars.append((var, episode['obj']))
            self.episodes_objs.append(episode['obj'])
        
        self.episodes_loaded = end_idx
        self.is_loading_episodes = False
        
        # Eğer daha fazla bölüm varsa "Daha Fazla Yükle" butonu ekle
        if self.episodes_loaded < len(self.all_episodes):
            load_more_frame = ctk.CTkFrame(self.episodes_list, fg_color="transparent")
            load_more_frame.pack(fill="x", padx=10, pady=10)
            
            load_more_btn = ctk.CTkButton(load_more_frame, text="Daha Fazla Bölüm Yükle",
                                        command=self.load_more_episodes)
            load_more_btn.pack()

    def render_episodes_page(self):
        """Bölümleri sayfalama ile göster."""
        # Discord Rich Presence güncelle
        if hasattr(self, 'selected_anime') and self.selected_anime:
            anime_title = self.selected_anime.get('title', {}).get('romaji', 'Bilinmeyen Anime')
            self.update_discord_presence(f"{anime_title} bölümlerine bakıyor", "TürkAnimu GUI")
        
        try:
            # Loading label'ı kaldır
            for widget in self.episodes_list.winfo_children():
                if hasattr(widget, 'cget') and widget.cget('text') == "Bölümler yükleniyor…":
                    widget.destroy()
                    break
        except:
            pass

        if not self.all_episodes:
            # Bölüm bulunamadı - manuel arama ekle
            not_found_frame = ctk.CTkFrame(self.episodes_list, fg_color="transparent")
            not_found_frame.pack(fill="x", padx=10, pady=10)
            
            not_found_label = ctk.CTkLabel(not_found_frame, 
                                         text=f"{self.selected_source} kaynağında bölüm bulunamadı",
                                         text_color="#ff6b6b")
            not_found_label.pack(pady=(0, 10))
            
            # Manuel arama kutusu
            search_frame = ctk.CTkFrame(not_found_frame, fg_color="#2a2a2a")
            search_frame.pack(fill="x", pady=(0, 10))
            
            search_entry = ctk.CTkEntry(search_frame, placeholder_text="Bu kaynakta ara...",
                                      width=250)
            search_entry.pack(side="left", padx=10, pady=10)
            
            def manual_search():
                search_query = search_entry.get().strip()
                if not search_query:
                    return
                
                # Arama butonunu devre dışı bırak
                search_btn.configure(state="disabled", text="Aranıyor...")
                
                def search_worker():
                    try:
                        search_results = []
                        if self.selected_source == "TürkAnime":
                            from turkanime_api.objects import Anime
                            all_list = Anime.get_anime_listesi()
                            for slug, name in all_list:
                                if search_query.lower() in (name or "").lower():
                                    search_results.append({"source": "TürkAnime", "slug": slug, "title": name})
                        else:
                            for _id, name in search_animecix(search_query):
                                search_results.append({"source": "AnimeciX", "id": int(_id), "title": name})
                        
                        self.after(0, lambda: show_search_results(search_results))
                    except Exception as e:
                        self.after(0, lambda: self.message(f"Arama hatası: {e}", error=True))
                        self.after(0, lambda: search_btn.configure(state="normal", text="🔍 Ara"))
                
                threading.Thread(target=search_worker, daemon=True).start()
            
            def show_search_results(results):
                search_btn.configure(state="normal", text="🔍 Ara")
                if not results:
                    self.message("Arama sonucu bulunamadı", error=True)
                    return
                
                # Sonuçları göster
                results_window = ctk.CTkToplevel(self)
                results_window.title(f"{self.selected_source} Arama Sonuçları")
                results_window.geometry("600x400")
                
                results_frame = ctk.CTkScrollableFrame(results_window, fg_color="transparent")
                results_frame.pack(fill="both", expand=True, padx=10, pady=10)
                
                for result in results[:10]:  # İlk 10 sonucu göster
                    result_btn = ctk.CTkButton(results_frame, 
                                             text=result["title"],
                                             command=lambda r=result: select_manual_result(r, results_window))
                    result_btn.pack(fill="x", pady=2)
            
            def select_manual_result(result, window):
                window.destroy()
                # Seçili sonucu işle
                if result["source"] == "TürkAnime":
                    ani = Anime(result["slug"])
                    manual_items = [{"title": b.title, "obj": b} for b in ani.bolumler]
                else:
                    cix = CixAnime(id=int(result["id"]), title=result["title"])
                    eps = cix.episodes
                    ada = AdapterAnime(slug=str(cix.id), title=cix.title)
                    manual_items = [{"title": e.title, "obj": AdapterBolum(url=e.url, title=e.title, anime=ada)} for e in eps]
                
                # Eski içeriği temizle ve yeni bölümleri göster
                for widget in self.episodes_list.winfo_children():
                    widget.destroy()
                
                if manual_items:
                    self.all_episodes = manual_items
                    self.episodes_loaded = 0
                    self.load_more_episodes()
                else:
                    ctk.CTkLabel(self.episodes_list, text="Bu anime için bölüm bulunamadı",
                               text_color="#ff6b6b").pack(pady=10)
            
            search_btn = ctk.CTkButton(search_frame, text="🔍 Ara", width=80,
                                     command=manual_search)
            search_btn.pack(side="left", padx=(0, 10), pady=10)
            
            return
        
        # İlk sayfayı yükle
        self.episodes_loaded = 0
        self.load_more_episodes()



    def toggle_anilist_panel(self):
        """AniList panelini göster/gizle."""
        if self.anilist_visible:
            # Gizle
            self.anilist_panel.pack_forget()
            self.btnAniListToggle.configure(text="👤 Göster")
            self.anilist_visible = False
        else:
            # Göster
            self.anilist_panel.pack(side="left", padx=(0, 2))
            self.btnAniListToggle.configure(text="👤 Gizle")
            self.anilist_visible = True

    def show_user_tooltip(self, event):
        """Avatar'a hover yapıldığında kullanıcı adını göster."""
        if hasattr(self, 'anilist_user') and self.anilist_user:
            username = self.anilist_user.get('name', 'Unknown')
            # Tooltip benzeri efekt için label rengini değiştir
            self.lblAniListUser.configure(text_color="#ff6b6b", font=ctk.CTkFont(size=10, weight="bold"))

    def hide_user_tooltip(self, event):
        """Kullanıcı tooltip'ini gizle."""
        if hasattr(self, 'user_tooltip') and self.user_tooltip:
            self.user_tooltip.destroy()
            self.user_tooltip = None
        # Label rengini geri döndür
        self.lblAniListUser.configure(text_color="#cccccc", font=ctk.CTkFont(size=9))

    def open_anilist_page(self, anilist_id):
        """AniList sayfasını tarayıcıda aç."""
        try:
            import webbrowser
            url = f"https://anilist.co/anime/{anilist_id}"
            webbrowser.open(url)
            self.message("AniList sayfası açılıyor...", error=False)
        except Exception as e:
            self.message(f"AniList sayfası açılamadı: {e}", error=True)


def run():
    sep = ";" if os.name == "nt" else ":"
    path_parts = [os.environ.get("PATH", "")]
    # Kullanıcı app verisi
    try:
        path_parts.append(Dosyalar().ta_path)
    except:
        pass
    # PyInstaller içindeysek _MEIPASS/bin
    try:
        _meipass = getattr(sys, "_MEIPASS", None)
        if _meipass:
            path_parts.append(os.path.join(_meipass, "bin"))
    except Exception:
        pass
    # Geliştirme ortamında proje kökü altındaki bin
    try:
        root_bin = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "bin")
        if os.path.isdir(root_bin):
            path_parts.append(root_bin)
    except Exception:
        pass
    os.environ["PATH"] = sep.join([p for p in path_parts if p])

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = MainWindow()
    
    # Uygulama kapanırken Discord bağlantısını kapat
    def on_closing():
        try:
            # Discord Rich Presence'i temizle
            if hasattr(app, 'disconnect_discord_rpc'):
                app.disconnect_discord_rpc()
            elif hasattr(app, 'discord_rpc') and app.discord_rpc:
                app.discord_rpc.clear()
                app.discord_rpc.close()
        except Exception as e:
            print(f"Uygulama kapanırken Discord RPC kapatma hatası: {e}")

        # Timer'ları iptal et
        try:
            if hasattr(app, 'discord_update_timer') and app.discord_update_timer:
                app.after_cancel(app.discord_update_timer)
        except Exception:
            pass

        app.destroy()
    
    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()


if __name__ == "__main__":
    run()