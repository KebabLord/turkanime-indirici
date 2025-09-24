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
from turkanime_api.common.db import APIManager
from turkanime_api.common.adapters import SearchEngine

# SearchEngine instance oluştur
search_engine = SearchEngine()

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
                    # _id'yi güvenli şekilde int'e çevir
                    try:
                        safe_id = int(_id)
                    except (ValueError, TypeError):
                        safe_id = hash(str(_id)) % 1000000
                    results.append({"source": "AnimeciX", "id": safe_id, "title": name})
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
                    # anime_id'yi güvenli şekilde int'e çevir
                    try:
                        safe_anime_id = int(anime_id)
                    except (ValueError, TypeError):
                        # String ID ise hash değeri al
                        safe_anime_id = hash(str(anime_id)) % 1000000

                    cix = CixAnime(id=str(safe_anime_id), title=anime_title)
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

        # Episodes listesi için değişkenler
        self.episodes_vars = []  # [(var, obj)]
        self.episodes_objs = []
        self.episodes_list = None
        self.source_accordion = None

        # Discord Rich Presence değişkenleri
        self.discord_rpc = None
        self.discord_connected = False
        self.discord_update_timer = None

        # Manager değişkenleri
        self.requirements_manager: Optional[RequirementsManager] = None
        self.update_manager: Optional[UpdateManager] = None

        # Performans iyileştirmesi: UI'yi adım adım yükle
        self._init_ui_async()

    def _init_ui_async(self):
        """UI'yi adım adım yükleyerek performans iyileştirmesi."""
        # İlk adım: Temel yapıyı oluştur
        self._create_basic_structure()

        # İkinci adım: Ana içeriği oluştur (50ms sonra)
        self.after(50, self._create_main_content)

        # Üçüncü adım: Gereksinimler ve güncellemeleri kontrol et (100ms sonra)
        self.after(100, self._create_requirements_and_updates)

        # Dördüncü adım: Discord RPC'yi başlat (150ms sonra)
        self.after(150, self._init_discord_async)

    def _create_basic_structure(self):
        """Temel UI yapısını oluştur."""
        # Ana container
        self.main_container = ctk.CTkFrame(self, fg_color="#0f0f0f")
        self.main_container.pack(fill="both", expand=True)

        # Header/Navigation
        self.create_header()

        # Ana içerik alanı
        self.content_area = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        self.content_area.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # UI güncellemesi için update_idletasks kullan
        self.update_idletasks()

    def _create_main_content(self):
        """Ana içeriği oluştur."""
        # Ana sayfa içeriği
        self.create_home_content()

        # Alt bar
        self.create_bottom_bar()

        # UI güncellemesi için update_idletasks kullan
        self.update_idletasks()

    def _create_requirements_and_updates(self):
        """Gereksinimler ve güncellemeleri thread ile başlat."""
        # Gereksinimler kontrolü - thread ile
        def init_requirements():
            try:
                self.requirements_manager = RequirementsManager(self)
                self.update_manager = UpdateManager(self, current_version="1.0.0")
                # Ana thread'de çalıştır
                self.after(0, self.check_requirements_on_startup)
            except Exception as e:
                print(f"Gereksinimler başlatma hatası: {e}")

        # Thread ile başlat
        threading.Thread(target=init_requirements, daemon=True).start()

        # UI güncellemesi için update_idletasks kullan
        self.update_idletasks()

    def _init_discord_async(self):
        """Discord RPC'yi başlat."""
        # Discord Rich Presence'i başlat - thread ile
        def init_discord():
            try:
                # Ana thread'de çalıştır
                self.after(0, self.init_discord_rpc)
            except Exception as e:
                print(f"Discord RPC başlatma hatası: {e}")

        # Thread ile başlat
        threading.Thread(target=init_discord, daemon=True).start()

        # UI güncellemesi için update_idletasks kullan
        self.update_idletasks()

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

        # Başlık seçimi
        title_frame = ctk.CTkFrame(search_frame, fg_color="transparent")
        title_frame.pack(side="left", padx=(0, 8))

        title_label = ctk.CTkLabel(title_frame, text="Başlık:",
                                  font=ctk.CTkFont(size=9, weight="bold"))
        title_label.pack(side="left", padx=(0, 5))

        self.cmbTitle = ctk.CTkComboBox(title_frame, values=["🇺🇸 İngilizce: Bilinmiyor", "🇯🇵 Romanji: Bilinmiyor"],
                                       width=150, height=32,
                                       command=self.on_title_change)
        self.cmbTitle.pack(side="left")

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
                    if self.requirements_manager:
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

    def open_anime_search_dialog(self):
        """Anime arama diyalog penceresi aç."""
        # Dialog penceresi oluştur
        dialog = ctk.CTkToplevel(self)
        dialog.title("Anime Ara")
        dialog.geometry("600x500")
        dialog.transient(self)
        dialog.grab_set()

        # Başlık
        title_label = ctk.CTkLabel(dialog, text="🔍 Anime Ara",
                                 font=ctk.CTkFont(size=20, weight="bold"),
                                 text_color="#ffffff")
        title_label.pack(pady=(20, 10))

        # Arama giriş alanı
        search_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        search_frame.pack(fill="x", padx=20, pady=(0, 10))

        search_label = ctk.CTkLabel(search_frame, text="Anime adı:",
                                  font=ctk.CTkFont(size=14))
        search_label.pack(anchor="w", pady=(0, 5))

        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Anime adını yazın...",
                                       font=ctk.CTkFont(size=14), height=40)
        self.search_entry.pack(fill="x", pady=(0, 10))
        self.search_entry.focus()

        # Adaptör seçimi
        adapter_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        adapter_frame.pack(fill="x", padx=20, pady=(0, 10))

        adapter_label = ctk.CTkLabel(adapter_frame, text="Arama Kaynağı:",
                                   font=ctk.CTkFont(size=14))
        adapter_label.pack(anchor="w", pady=(0, 5))

        # Mevcut kaynak seçimini kullan (TürkAnime/AnimeciX)
        current_source = getattr(self, 'selected_source', 'AnimeciX')
        adapter_options = ["AnimeciX", "TürkAnime", "AniList"]
        self.adapter_combo = ctk.CTkComboBox(adapter_frame, values=adapter_options,
                                           width=200, height=35,
                                           command=self._on_adapter_change)
        self.adapter_combo.pack(side="left", padx=(0, 10))

        # Varsayılan seçimi ayarla
        if current_source in adapter_options:
            self.adapter_combo.set(current_source)
        else:
            self.adapter_combo.set("AnimeciX")

        # Kaynak değiştir butonu
        switch_btn = ctk.CTkButton(adapter_frame, text="🔄 Kaynak Değiştir",
                                 command=self._switch_search_source,
                                 fg_color="#4ecdc4", hover_color="#45b7aa",
                                 width=120, height=35)
        switch_btn.pack(side="left")

        # Sonuç listesi
        results_frame = ctk.CTkFrame(dialog, fg_color="#1a1a1a")
        results_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        results_label = ctk.CTkLabel(results_frame, text="Arama Sonuçları:",
                                   font=ctk.CTkFont(size=14, weight="bold"))
        results_label.pack(anchor="w", padx=15, pady=(15, 10))

        # Scrollable frame for results
        self.results_scrollable = ctk.CTkScrollableFrame(results_frame, fg_color="transparent")
        self.results_scrollable.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Loading label
        self.loading_label = ctk.CTkLabel(self.results_scrollable, text="Arama yapmak için yazmaya başlayın...",
                                        font=ctk.CTkFont(size=12),
                                        text_color="#888888")
        self.loading_label.pack(pady=20)

        # Butonlar
        buttons_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=20, pady=(0, 20))

        cancel_btn = ctk.CTkButton(buttons_frame, text="❌ İptal",
                                 command=dialog.destroy,
                                 fg_color="#666666", width=100)
        cancel_btn.pack(side="right")

        # Arama değişkenlerini sakla
        self.search_timer = None
        self.current_results = []

        # Event binding - arama girişi değiştiğinde
        self.search_entry.bind("<KeyRelease>", lambda e: self._on_search_input_change(dialog))

        # Dialog'u ortala
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
        y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        # Dialog kapatıldığında timer'ı iptal et
        def on_dialog_close():
            if hasattr(self, 'search_timer') and self.search_timer:
                self.after_cancel(self.search_timer)
                self.search_timer = None
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)

    def _on_adapter_change(self, selected_adapter):
        """Adaptör seçildiğinde çağrılır."""
        self.selected_search_adapter = selected_adapter
        print(f"Seçilen arama adaptörü: {selected_adapter}")

    def _switch_search_source(self):
        """Arama kaynağını değiştir."""
        if hasattr(self, 'selected_search_adapter'):
            # Ana uygulama kaynağını güncelle
            if self.selected_search_adapter in ["TürkAnime", "AnimeciX"]:
                self.selected_source = self.selected_search_adapter
                # Ana kaynak selector'ünü güncelle
                if hasattr(self, 'cmbSource'):
                    self.cmbSource.set(self.selected_search_adapter)
                self.message(f"Arama kaynağı {self.selected_search_adapter} olarak değiştirildi!")
            else:
                self.message("Bu kaynak sadece arama için kullanılabilir", error=True)

    def _on_search_input_change(self, dialog):
        """Arama girişi değiştiğinde çağrılır."""
        # Önceki timer'ı iptal et
        if hasattr(self, 'search_timer') and self.search_timer:
            self.after_cancel(self.search_timer)

        # Yeni timer başlat (300ms gecikme)
        self.search_timer = self.after(300, lambda: self._perform_search(dialog))

    def _perform_search(self, dialog):
        """Anime arama işlemini gerçekleştir - tüm kaynaklarda paralel arama."""
        query = self.search_entry.get().strip()
        if not query or len(query) < 2:
            self._clear_results()
            self.loading_label.configure(text="En az 2 karakter yazın...")
            self.loading_label.pack(pady=20)
            return

        # Loading göster
        self._clear_results()
        self.loading_label.configure(text="🔍 Tüm kaynaklarda aranıyor...")
        self.loading_label.pack(pady=20)

        # Arama işlemini thread'de çalıştır
        def search_worker():
            try:
                # Tüm kaynaklarda paralel arama yap
                all_results = search_engine.search_all_sources(query, limit_per_source=10)

                # Sonuçları birleştir ve kaynak bilgisi ekle
                combined_results = []
                for source_name, results in all_results.items():
                    for anime_id, anime_name in results:
                        combined_results.append({
                            'id': anime_id,
                            'name': anime_name,
                            'source': source_name
                        })

                # Ana thread'de sonuçları göster
                self.after(0, lambda: self._display_combined_search_results(combined_results, dialog))
            except Exception as e:
                self.after(0, lambda err=e: self._show_search_error(str(err), dialog))

        threading.Thread(target=search_worker, daemon=True).start()

    def _clear_results(self):
        """Sonuçları temizle."""
        # Mevcut sonuç widget'larını temizle
        for widget in self.results_scrollable.winfo_children():
            if widget != self.loading_label:
                widget.destroy()

    def _display_search_results(self, results, dialog):
        """Arama sonuçlarını göster."""
        self._clear_results()
        self.current_results = results

        if not results:
            no_results = ctk.CTkLabel(self.results_scrollable, text="Sonuç bulunamadı",
                                    font=ctk.CTkFont(size=14),
                                    text_color="#888888")
            no_results.pack(pady=20)
            return

        # Sonuçları göster
        for i, (anime_id, anime_name) in enumerate(results[:20]):  # Max 20 sonuç
            result_frame = ctk.CTkFrame(self.results_scrollable, fg_color="#2a2a2a",
                                       border_width=1, border_color="#444444")
            result_frame.pack(fill="x", pady=2, padx=5)

            # Anime adı
            name_label = ctk.CTkLabel(result_frame, text=anime_name,
                                    font=ctk.CTkFont(size=13),
                                    text_color="#ffffff",
                                    anchor="w")
            name_label.pack(side="left", fill="x", expand=True, padx=10, pady=8)

            # ID göster
            id_label = ctk.CTkLabel(result_frame, text=f"#{anime_id}",
                                  font=ctk.CTkFont(size=11),
                                  text_color="#cccccc")
            id_label.pack(side="right", padx=10, pady=8)

            # Tıklama eventi
            def make_click_handler(aid=anime_id, aname=anime_name, dlg=dialog):
                return lambda e: self._on_anime_selected(aid, aname, dlg)

            result_frame.bind("<Button-1>", make_click_handler(aid=anime_id, aname=anime_name, dlg=dialog))
            name_label.bind("<Button-1>", make_click_handler(aid=anime_id, aname=anime_name, dlg=dialog))
            id_label.bind("<Button-1>", make_click_handler(aid=anime_id, aname=anime_name, dlg=dialog))

            # Hover efekti
            def on_enter(e, frame=result_frame):
                frame.configure(fg_color="#3a3a3a")

            def on_leave(e, frame=result_frame):
                frame.configure(fg_color="#2a2a2a")

            result_frame.bind("<Enter>", on_enter)
            result_frame.bind("<Leave>", on_leave)

    def _display_combined_search_results(self, results, dialog):
        """Birleştirilmiş arama sonuçlarını göster - kaynak bilgisi ile."""
        self._clear_results()
        self.current_results = results

        if not results:
            no_results = ctk.CTkLabel(self.results_scrollable, text="Sonuç bulunamadı",
                                    font=ctk.CTkFont(size=14),
                                    text_color="#888888")
            no_results.pack(pady=20)
            return

        # Sonuçları kaynaklara göre grupla
        source_groups = {}
        for result in results:
            source = result['source']
            if source not in source_groups:
                source_groups[source] = []
            source_groups[source].append(result)

        # Her kaynak için sonuçları göster
        for source_name, source_results in source_groups.items():
            # Kaynak başlığı
            source_label = ctk.CTkLabel(self.results_scrollable,
                                      text=f"📺 {source_name} ({len(source_results)} sonuç)",
                                      font=ctk.CTkFont(size=14, weight="bold"),
                                      text_color="#4ecdc4")
            source_label.pack(anchor="w", padx=5, pady=(10, 5))

            # Kaynak sonuçları
            for result in source_results[:10]:  # Kaynak başına max 10 sonuç
                result_frame = ctk.CTkFrame(self.results_scrollable, fg_color="#2a2a2a",
                                           border_width=1, border_color="#444444")
                result_frame.pack(fill="x", pady=2, padx=10)

                # Anime adı
                name_label = ctk.CTkLabel(result_frame, text=result['name'],
                                        font=ctk.CTkFont(size=13),
                                        text_color="#ffffff",
                                        anchor="w")
                name_label.pack(side="left", fill="x", expand=True, padx=10, pady=8)

                # Kaynak ve ID göster
                info_label = ctk.CTkLabel(result_frame,
                                        text=f"{result['source']} #{result['id']}",
                                        font=ctk.CTkFont(size=11),
                                        text_color="#cccccc")
                info_label.pack(side="right", padx=10, pady=8)

                # Tıklama eventi
                def make_click_handler(aid=result['id'], aname=result['name'],
                                     source=result['source'], dlg=dialog):
                    return lambda e: self._on_anime_selected_with_source(aid, aname, source, dlg)

                result_frame.bind("<Button-1>", make_click_handler(aid=result['id'],
                                                                aname=result['name'],
                                                                source=result['source'], dlg=dialog))
                name_label.bind("<Button-1>", make_click_handler(aid=result['id'],
                                                               aname=result['name'],
                                                               source=result['source'], dlg=dialog))
                info_label.bind("<Button-1>", make_click_handler(aid=result['id'],
                                                               aname=result['name'],
                                                               source=result['source'], dlg=dialog))

                # Hover efekti
                def on_enter(e, frame=result_frame):
                    frame.configure(fg_color="#3a3a3a")

                def on_leave(e, frame=result_frame):
                    frame.configure(fg_color="#2a2a2a")

                result_frame.bind("<Enter>", on_enter)
                result_frame.bind("<Leave>", on_leave)

    def _show_search_error(self, error_msg, dialog):
        """Arama hatası göster."""
        self._clear_results()
        error_label = ctk.CTkLabel(self.results_scrollable,
                                 text=f"Arama hatası: {error_msg}",
                                 font=ctk.CTkFont(size=12),
                                 text_color="#ff6b6b")
        error_label.pack(pady=20)

    def _on_anime_selected(self, anime_id, anime_name, dialog):
        """Anime seçildiğinde çağrılır."""
        try:
            # JSON dosyasına kaydet
            self._save_anime_to_json(anime_id, anime_name)

            # Ana pencereyle eşleştir
            self._match_anime_with_main(anime_id, anime_name)

            # Dialog'u kapat
            dialog.destroy()

            # Başarı mesajı
            self.message(f"'{anime_name}' seçildi ve kaydedildi!")

        except Exception as e:
            self.message(f"Anime seçme hatası: {e}", error=True)

    def _on_anime_selected_with_source(self, anime_id, anime_name, source, dialog):
        """Kaynak bilgisi ile anime seçildiğinde çağrılır."""
        try:
            # JSON dosyasına kaydet
            self._save_anime_to_json(anime_id, anime_name)

            # Veritabanına kaydet (eğer API mevcutsa)
            try:
                db = APIManager()
                db.save_anime_match(source, anime_id, anime_name)
            except Exception as db_e:
                print(f"API kaydetme hatası (normal): {db_e}")

            # Ana pencereyle eşleştir - kaynak bilgisi ile
            self._match_anime_with_main_and_source(anime_id, anime_name, source)

            # Dialog'u kapat
            dialog.destroy()

            # Başarı mesajı
            self.message(f"'{anime_name}' ({source}) seçildi ve kaydedildi!")

        except Exception as e:
            self.message(f"Anime seçme hatası: {e}", error=True)

    def _save_anime_to_json(self, anime_id, anime_name):
        """Anime'yi anime_names.json dosyasına kaydet."""
        try:
            json_path = os.path.join(os.path.dirname(__file__), "anime_names.json")

            # Mevcut veriyi oku
            existing_data = {}
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    existing_data = {}

            # Tekrar eden kayıt kontrolü
            if str(anime_id) in existing_data:
                # Zaten varsa güncelleme yap
                existing_data[str(anime_id)]['name'] = anime_name
                existing_data[str(anime_id)]['last_updated'] = time.time()
            else:
                # Yeni kayıt ekle
                existing_data[str(anime_id)] = {
                    'name': anime_name,
                    'added_date': time.time(),
                    'last_updated': time.time()
                }

            # JSON dosyasına yaz
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            raise Exception(f"JSON kaydetme hatası: {e}")

    def _match_anime_with_main(self, anime_id, anime_name):
        """Seçilen anime'yi ana pencereyle eşleştir."""
        try:
            # Animecix'ten detayları al
            from turkanime_api.sources.animecix import CixAnime

            # anime_id'yi güvenli şekilde int'e çevir
            safe_anime_id = self._safe_int_conversion(anime_id)

            # Yeni anime nesnesi oluştur
            anime_obj = CixAnime(str(safe_anime_id), anime_name)

            # AniList eşleştirmesi için basit veri oluştur
            anilist_data = {
                'id': safe_anime_id,
                'title': {
                    'romaji': anime_name,
                    'english': anime_name
                },
                'episodes': None,  # Bilinmiyor
                'coverImage': {'large': None},
                'averageScore': None,
                'popularity': None,
                'description': f"{anime_name} - Animecix'ten eklendi"
            }

            # Ana pencerede göster
            self.show_anime_details(anilist_data)

        except Exception as e:
            raise Exception(f"Ana pencere eşleştirme hatası: {e}")

    def _safe_int_conversion(self, value, default=0):
        """Güvenli int dönüşümü - string ID'ler için."""
        try:
            return int(value)
        except (ValueError, TypeError):
            # String ID ise hash değeri al veya default kullan
            if isinstance(value, str) and value:
                # String ID için basit bir hash oluştur
                return hash(value) % 1000000  # 6 haneli sayı
            return default

    def _match_anime_with_main_and_source(self, anime_id, anime_name, source):
        """Kaynak bilgisi ile seçilen anime'yi ana pencereyle eşleştir."""
        try:
            # anime_id'yi güvenli şekilde int'e çevir
            safe_anime_id = self._safe_int_conversion(anime_id)

            # Kaynağa göre uygun anime nesnesi oluştur
            if source == "AnimeciX":
                from turkanime_api.sources.animecix import CixAnime
                anime_obj = CixAnime(str(safe_anime_id), anime_name)
                anilist_data = {
                    'id': safe_anime_id,
                    'title': {
                        'romaji': anime_name,
                        'english': anime_name
                    },
                    'episodes': len(anime_obj.episodes) if hasattr(anime_obj, 'episodes') else None,
                    'coverImage': {'large': None},
                    'averageScore': None,
                    'popularity': None,
                    'description': f"{anime_name} - {source}'ten eklendi"
                }

            elif source == "TürkAnime":
                from turkanime_api.objects import Anime
                anime_obj = Anime(anime_id)  # TürkAnime string ID kabul edebilir
                anilist_data = {
                    'id': safe_anime_id,
                    'title': {
                        'romaji': anime_obj.title if hasattr(anime_obj, 'title') else anime_name,
                        'english': anime_name
                    },
                    'episodes': len(anime_obj.bolumler) if hasattr(anime_obj, 'bolumler') else None,
                    'coverImage': {'large': None},
                    'averageScore': None,
                    'popularity': None,
                    'description': f"{anime_name} - {source}'ten eklendi"
                }

            elif source == "AniList":
                # AniList için adaptör kullanarak detayları al
                adapter = search_engine.get_adapter("AniList")
                anime_details = None
                if adapter:
                    anime_details = adapter.get_anime_details(str(anime_id))
                if anime_details:
                    anilist_data = {
                        'id': safe_anime_id,
                        'title': {
                            'romaji': anime_details.get('title', anime_name),
                            'english': anime_name
                        },
                        'episodes': anime_details.get('episodes'),
                        'coverImage': {'large': None},
                        'averageScore': None,
                        'popularity': None,
                        'description': f"{anime_name} - {source}'ten eklendi"
                    }
                else:
                    # Fallback
                    anilist_data = {
                        'id': safe_anime_id,
                        'title': {
                            'romaji': anime_name,
                            'english': anime_name
                        },
                        'episodes': None,
                        'coverImage': {'large': None},
                        'averageScore': None,
                        'popularity': None,
                        'description': f"{anime_name} - {source}'ten eklendi"
                    }

            else:
                # Bilinmeyen kaynak için varsayılan
                anilist_data = {
                    'id': safe_anime_id,
                    'title': {
                        'romaji': anime_name,
                        'english': anime_name
                    },
                    'episodes': None,
                    'coverImage': {'large': None},
                    'averageScore': None,
                    'popularity': None,
                    'description': f"{anime_name} - {source}'ten eklendi"
                }

            # Ana pencerede göster
            self.show_anime_details(anilist_data)

        except Exception as e:
            raise Exception(f"Ana pencere eşleştirme hatası ({source}): {e}")

    def get_anime_titles(self):
        """Mevcut anime'den başlıkları al (Romanji, İngilizce, vb.)"""
        titles = []
        
        if hasattr(self, 'selected_anime') and self.selected_anime:
            anime_data = self.selected_anime
            title_data = anime_data.get('title', {})
            
            # Romanji başlığı
            romaji = title_data.get('romaji')
            if romaji:
                titles.append(f"🇯🇵 Romanji: {romaji}")
            
            # İngilizce başlığı
            english = title_data.get('english')
            if english:
                titles.append(f"🇺🇸 İngilizce: {english}")
            
            # Diğer diller
            native = title_data.get('native')
            if native:
                titles.append(f"🇯🇵 Orijinal: {native}")
        
        # Eğer hiç başlık yoksa varsayılan ekle
        if not titles:
            titles = ["🇺🇸 İngilizce: Bilinmiyor", "🇯🇵 Romanji: Bilinmiyor"]
        
        return titles

    def update_title_selector(self):
        """Başlık selector'ünü güncelle."""
        if hasattr(self, 'cmbTitle'):
            titles = self.get_anime_titles()
            self.cmbTitle.configure(values=titles)
            
            # Default olarak İngilizce'yi seç
            english_title = None
            for title in titles:
                if "İngilizce:" in title:
                    english_title = title
                    break
            
            if english_title:
                self.cmbTitle.set(english_title)
            elif titles:
                self.cmbTitle.set(titles[0])

    def on_title_change(self, selected_title):
        """Başlık seçildiğinde çağrılır."""
        if selected_title:
            # Seçilen başlığı sakla
            self.selected_title = selected_title
            print(f"Seçilen başlık: {selected_title}")

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
        with open("debug.log", "a") as f:
            f.write(f"DEBUG: show_anime_details çağrıldı: {anime_data.get('title', {}).get('romaji', 'Unknown')}\n")
        # Detay görünümü oluştur
        self.clear_content_area()
        # Seçili animeyi sakla (global oynat/indir butonları için)
        self.selected_anime = anime_data

        # Başlık selector'ünü güncelle
        self.update_title_selector()

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
            self.btnAniListPage.pack(side="left", padx=(0, 10))

        # Özel anime arama butonu - sadece bölüm bulunamadığında gösterilsin
        self.btnCustomSearch = ctk.CTkButton(buttons_frame, text="🔍 İstediğin Anime Değil Mi?",
                                          command=self.open_anime_search_dialog,
                                          fg_color="transparent", border_width=2,
                                          border_color="#ffd93d", text_color="#ffd93d",
                                          width=180, height=40,
                                          font=ctk.CTkFont(size=12, weight="bold"),
                                          corner_radius=20)
        # Başlangıçta gizli
        self.btnCustomSearch.pack_forget()

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

        # Bölümler bölümü (Kaynaklar accordion içinde)
        episodes_section = ctk.CTkFrame(details_frame, fg_color="transparent")
        episodes_section.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        ep_title_row = ctk.CTkFrame(episodes_section, fg_color="transparent")
        ep_title_row.pack(fill="x")
        ep_title = ctk.CTkLabel(ep_title_row, text="",
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
                                      command=self.open_anime_search_dialog)
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
        self.all_episodes = {}  # Kaynak bazlı bölümler: {"AniList": [...], "TürkAnime": [...], "AnimeciX": [...]}

        ep_loading = ctk.CTkLabel(self.episodes_list, text="Kaynaklar yükleniyor…",
                                  font=ctk.CTkFont(size=14), text_color="#cccccc")
        ep_loading.pack(pady=20)

        # Başlık adayı: romaji -> english fallback
        romaji = anime_data.get('title', {}).get('romaji') or ""
        english = anime_data.get('title', {}).get('english') or ""
        query_title = romaji if romaji else english

        # DB'den önceki eşleşmeleri kontrol et
        db_matches = self._load_anime_matches_from_db(query_title)

        def load_sources_worker():
            """Kaynakları yükle - SearchEngine ile ve timeout atlama ile."""
            with open("debug.log", "a") as f:
                f.write("DEBUG: load_sources_worker başladı\n")
            try:
                # Tüm kaynaklarda paralel arama yap
                sources_data = {}
                source_status = {}  # Her kaynağın durumunu takip et
                source_timeouts = {
                    "TürkAnime": 8,   # 8 saniye
                    "AnimeciX": 8,    # 8 saniye
                    "AniList": 5      # 5 saniye (daha hızlı)
                }

                def search_source_with_timeout(source_name, timeout_seconds):
                    """Kaynak arama işlemi - timeout ile ve hata loglaması ile."""
                    def timeout_handler():
                        """Timeout durumunda çağrılır."""
                        if source_status.get(source_name) == "loading":
                            source_status[source_name] = "timeout"
                            sources_data[source_name] = []
                            with open("debug.log", "a") as f:
                                f.write(f"ERROR: {source_name} timeout ({timeout_seconds}s) - kaynak atlandı\n")

                    # Timeout timer'ı başlat
                    timer = threading.Timer(timeout_seconds, timeout_handler)
                    timer.start()

                    try:
                        source_status[source_name] = "loading"
                        start_time = time.time()
                        with open("debug.log", "a") as f:
                            f.write(f"DEBUG: {source_name} araması başlatılıyor (timeout: {timeout_seconds}s)\n")

                        if source_name == "AniList":
                            # AniList'te ara (sadece bilgi amaçlı)
                            results = anilist_client.search_anime(query_title, per_page=1)
                            if results:
                                anime_data = results[0]
                                sources_data[source_name] = [{"title": anime_data.get('title', {}).get('romaji'), "obj": anime_data, "anime_title": anime_data.get('title', {}).get('romaji')}]
                                source_status[source_name] = "completed"
                                with open("debug.log", "a") as f:
                                    f.write(f"DEBUG: {source_name} tamamlandı - {len(sources_data[source_name])} sonuç\n")
                            else:
                                source_status[source_name] = "no_results"
                                with open("debug.log", "a") as f:
                                    f.write(f"DEBUG: {source_name} - sonuç bulunamadı\n")

                        elif source_name == "TürkAnime":
                            # SearchEngine kullanarak TürkAnime'de ara
                            adapter = search_engine.get_adapter(source_name)
                            if adapter:
                                search_results = adapter.search_anime(query_title, limit=1)
                                if search_results:
                                    slug, name = search_results[0]
                                    # Anime objesi oluştur ve bölümleri al
                                    ani = Anime(slug)
                                    episodes = []
                                    for b in ani.bolumler:
                                        episodes.append({
                                            "title": b.title,
                                            "obj": b,
                                            "anime_title": name
                                        })
                                    sources_data[source_name] = episodes
                                    source_status[source_name] = "completed"
                                    with open("debug.log", "a") as f:
                                        f.write(f"DEBUG: {source_name} tamamlandı - {len(episodes)} bölüm\n")
                                else:
                                    source_status[source_name] = "no_results"
                                    with open("debug.log", "a") as f:
                                        f.write(f"DEBUG: {source_name} - sonuç bulunamadı\n")
                            else:
                                source_status[source_name] = "error"
                                with open("debug.log", "a") as f:
                                    f.write(f"ERROR: {source_name} adapter bulunamadı\n")

                        elif source_name == "AnimeciX":
                            # SearchEngine kullanarak AnimeciX'te ara
                            adapter = search_engine.get_adapter(source_name)
                            if adapter:
                                search_results = adapter.search_anime(query_title, limit=1)
                                if search_results:
                                    _id, name = search_results[0]
                                    # _id'yi güvenli şekilde int'e çevir
                                    try:
                                        safe_id = int(_id)
                                    except (ValueError, TypeError):
                                        safe_id = hash(str(_id)) % 1000000

                                    cix = CixAnime(id=str(safe_id), title=str(name))
                                    eps = cix.episodes
                                    episodes = []
                                    ada = AdapterAnime(slug=str(cix.id), title=cix.title)
                                    for e in eps:
                                        ab = AdapterBolum(url=e.url, title=e.title, anime=ada)
                                        episodes.append({
                                            "title": e.title,
                                            "obj": ab,
                                            "anime_title": name
                                        })
                                    sources_data[source_name] = episodes
                                    source_status[source_name] = "completed"
                                    with open("debug.log", "a") as f:
                                        f.write(f"DEBUG: {source_name} tamamlandı - {len(episodes)} bölüm\n")
                                else:
                                    source_status[source_name] = "no_results"
                                    with open("debug.log", "a") as f:
                                        f.write(f"DEBUG: {source_name} - sonuç bulunamadı\n")
                            else:
                                source_status[source_name] = "error"
                                with open("debug.log", "a") as f:
                                    f.write(f"ERROR: {source_name} adapter bulunamadı\n")

                        # Başarılı tamamlandı, timer'ı iptal et
                        timer.cancel()
                        elapsed_time = time.time() - start_time
                        with open("debug.log", "a") as f:
                            f.write(f"DEBUG: {source_name} tamamlandı: {elapsed_time:.2f}s\n")

                    except Exception as e:
                        # Timer'ı iptal et
                        timer.cancel()
                        elapsed_time = time.time() - start_time if 'start_time' in locals() else 0
                        with open("debug.log", "a") as f:
                            f.write(f"ERROR: {source_name} arama hatası ({elapsed_time:.2f}s): {str(e)}\n")
                        sources_data[source_name] = []
                        source_status[source_name] = "error"

                # Paralel arama - her kaynak için ayrı thread
                threads = []
                for source_name in ["TürkAnime", "AnimeciX", "AniList"]:
                    timeout = source_timeouts.get(source_name, 10)
                    thread = threading.Thread(
                        target=search_source_with_timeout,
                        args=(source_name, timeout),
                        daemon=True
                    )
                    threads.append(thread)
                    thread.start()

                # Tüm thread'lerin bitmesini bekle (maksimum toplam süre)
                total_timeout = 15  # Toplam maksimum 15 saniye
                start_total = time.time()

                for i, thread in enumerate(threads):
                    source_name = ["TürkAnime", "AnimeciX", "AniList"][i]
                    # Eğer bu kaynak zaten timeout olduysa, bekleme
                    if source_status.get(source_name) == "timeout":
                        with open("debug.log", "a") as f:
                            f.write(f"DEBUG: {source_name} zaten timeout oldu, beklenmiyor\n")
                        continue

                    remaining_time = total_timeout - (time.time() - start_total)
                    if remaining_time > 0:
                        thread.join(timeout=remaining_time)
                        # Thread hala çalışıyorsa ve timeout olduysa işaretle
                        if thread.is_alive() and source_status.get(source_name) != "completed":
                            source_status[source_name] = "timeout"
                            sources_data[source_name] = []
                            with open("debug.log", "a") as f:
                                f.write(f"ERROR: {source_name} thread timeout - kaynak atlandı\n")
                    else:
                        # Toplam timeout aşıldı
                        if source_status.get(source_name) != "completed":
                            source_status[source_name] = "timeout"
                            sources_data[source_name] = []
                        with open("debug.log", "a") as f:
                            f.write(f"ERROR: Toplam timeout ({total_timeout}s) aşıldı, {source_name} atlandı\n")

                # Hangi kaynakların tamamlandığını kontrol et ve logla
                completed_sources = [s for s, status in source_status.items() if status == "completed"]
                failed_sources = [s for s, status in source_status.items() if status in ["error", "timeout"]]
                no_results_sources = [s for s, status in source_status.items() if status == "no_results"]

                with open("debug.log", "a") as f:
                    if completed_sources:
                        f.write(f"INFO: Başarıyla yüklenen kaynaklar: {', '.join(completed_sources)}\n")
                    if failed_sources:
                        f.write(f"ERROR: Başarısız olan kaynaklar: {', '.join(failed_sources)}\n")
                    if no_results_sources:
                        f.write(f"INFO: Sonuç bulunmayan kaynaklar: {', '.join(no_results_sources)}\n")

                # Bölümleri sakla ve render et
                self.all_episodes = sources_data
                with open("debug.log", "a") as f:
                    f.write(f"DEBUG: all_episodes set to: {list(sources_data.keys())}\n")
                self.after(0, lambda: self._update_loading_status("Kaynaklar işleniyor..."))
                self.after(100, lambda: self.render_sources_page(db_matches))
                with open("debug.log", "a") as f:
                    f.write("DEBUG: render_sources_page scheduled\n")

            except Exception as e:
                with open("debug.log", "a") as f:
                    f.write(f"ERROR: load_sources_worker genel hata: {str(e)}\n")
                import traceback
                traceback.print_exc()
                # Hata durumunda boş veri ile devam et
                self.all_episodes = {}
                self.after(0, lambda: self.render_sources_page(db_matches))

        # Kaynak yükleme worker'ını başlat
        with open("debug.log", "a") as f:
            f.write("DEBUG: Thread başlatılıyor\n")
        worker_thread = threading.Thread(target=load_sources_worker, daemon=True)
        worker_thread.start()
        with open("debug.log", "a") as f:
            f.write("DEBUG: Thread başlatıldı\n")

        def _update_loading_status(self, message):
            """Loading durumunu güncelle."""
            try:
                # Loading label'ını bul ve güncelle
                if self.episodes_list:
                    for widget in self.episodes_list.winfo_children():
                        if hasattr(widget, 'configure') and hasattr(widget, 'cget'):
                            try:
                                current_text = widget.cget('text')
                                if "yükleniyor" in current_text.lower() or "işleniyor" in current_text.lower():
                                    widget.configure(text=message)
                                    break
                            except:
                                continue
            except Exception as e:
                print(f"Loading status güncelleme hatası: {e}")

        with open("debug.log", "a") as f:
            f.write("DEBUG: show_anime_details tamamlandı\n")

    def _check_and_correct_anime_name(self):
        """Anime adını API'den kontrol et ve gerekirse düzelt."""
        if not hasattr(self, 'selected_anime') or not self.selected_anime:
            return

        try:
            from turkanime_api.common.db import api_manager

            # Mevcut anime adını al
            current_name = self.selected_anime.get('title', {}).get('romaji', '') or \
                         self.selected_anime.get('title', {}).get('english', '') or \
                         self.selected_anime.get('title', {}).get('native', '')

            if not current_name:
                return

            # API'den eşleştirmeleri ara
            matches = api_manager.get_anime_matches(current_name)
            if not matches:
                return

            # En çok eşleştirilen anime adını bul
            name_counts = {}
            for match in matches:
                anime_title = match.get('anime_title', '')
                if anime_title:
                    name_counts[anime_title] = name_counts.get(anime_title, 0) + 1

            if not name_counts:
                return

            # En çok kullanılan anime adını al
            correct_name = max(name_counts.items(), key=lambda x: x[1])[0]

            # Eğer farklıysa güncelle
            if correct_name != current_name:
                print(f"Anime adı otomatik düzeltildi: {current_name} -> {correct_name}")

                # Anime adını güncelle
                if 'title' not in self.selected_anime:
                    self.selected_anime['title'] = {}
                self.selected_anime['title']['romaji'] = correct_name
                self.selected_anime['title']['english'] = correct_name
                self.selected_anime['title']['native'] = correct_name

                # Kullanıcıya bilgi ver
                self.message(f"Anime adı düzeltildi: {correct_name}", error=False)

        except Exception as e:
            print(f"Anime adı kontrolü hatası: {e}")

    def render_sources_page(self, db_matches=None):
        """Kaynakları accordion tarzında göster - performans iyileştirmesi ile."""
        with open("debug.log", "a") as f:
            f.write(f"DEBUG: render_sources_page çağrıldı, all_episodes: {list(self.all_episodes.keys()) if self.all_episodes else 'None'}\n")

        # Anime adı kontrolü ve otomatik düzeltme
        self._check_and_correct_anime_name()

        # Discord Rich Presence güncelle
        if hasattr(self, 'selected_anime') and self.selected_anime:
            anime_title = self.selected_anime.get('title', {}).get('romaji', 'Bilinmeyen Anime')
            self.update_discord_presence(f"{anime_title} kaynaklarına bakıyor", "TürkAnimu GUI")

        try:
            # Loading label'ı kaldır
            if self.episodes_list:
                for widget in self.episodes_list.winfo_children():
                    if hasattr(widget, 'cget') and widget.cget('text') == "Kaynaklar yükleniyor…":
                        widget.destroy()
                        break
        except:
            pass

        if not self.all_episodes or not any(episodes for episodes in self.all_episodes.values()):
            # Bölüm bulunamadı - koşullu butonu göster
            if hasattr(self, 'btnCustomSearch'):
                try:
                    self.btnCustomSearch.pack(side="left")
                except:
                    pass

            # Bölüm bulunamadı mesajı
            not_found_frame = ctk.CTkFrame(self.episodes_list, fg_color="transparent")
            not_found_frame.pack(fill="x", padx=10, pady=10)

            not_found_label = ctk.CTkLabel(not_found_frame,
                                         text="Hiçbir kaynakta bölüm bulunamadı",
                                         text_color="#ff6b6b")
            not_found_label.pack(pady=(0, 10))

            return

        # Sadece bölümler için kullanılacak kaynakları ayır (AniList hariç)
        display_sources = {k: v for k, v in self.all_episodes.items() if k in ["TürkAnime", "AnimeciX"]}

        # Kaynak durumlarını kontrol et ve kullanıcıya bildir
        loaded_sources = [k for k, v in display_sources.items() if v and len(v) > 0]
        failed_sources = [k for k in ["TürkAnime", "AnimeciX"] if k not in display_sources or not display_sources.get(k)]

        if loaded_sources:
            status_msg = f"✅ {len(loaded_sources)} kaynak yüklendi: {', '.join(loaded_sources)}"
            if failed_sources:
                status_msg += f"\n⚠️ {len(failed_sources)} kaynak yüklenemedi: {', '.join(failed_sources)}"
            self.message(status_msg, error=False)
        elif failed_sources:
            self.message(f"❌ Tüm kaynaklar yüklenemedi: {', '.join(failed_sources)}", error=True)

        # İlk adım: Loading mesajı göster
        if self.episodes_list:
            loading_frame = ctk.CTkFrame(self.episodes_list, fg_color="transparent")
            loading_frame.pack(fill="x", padx=10, pady=10)

            loading_label = ctk.CTkLabel(loading_frame, text="Bölümler hazırlanıyor...",
                                       font=ctk.CTkFont(size=14), text_color="#cccccc")
            loading_label.pack(pady=20)

        # UI güncellemesi için update_idletasks kullan
        self.update_idletasks()
        
        def create_accordion():
            try:
                with open("debug.log", "a") as f:
                    f.write("DEBUG: create_accordion başladı\n")
                # Loading frame'i kaldır
                loading_frame.destroy()
                
                # AccordionSourceEpisodeList ile kaynakları göster (sadece bölümler için)
                from turkanime_api.common.ui import AccordionSourceEpisodeList
                
                # Anime adını al
                anime_name = "unknown"
                if hasattr(self, 'selected_anime') and self.selected_anime:
                    anime_name = self.selected_anime.get('title', {}).get('romaji', 
                                self.selected_anime.get('title', {}).get('english', 
                                self.selected_anime.get('title', {}).get('native', 'unknown')))
                
                self.source_accordion = AccordionSourceEpisodeList(
                    self.episodes_list, display_sources, max_episodes_per_source=50,
                    on_play=self._play_episode, on_download=self._download_episode,
                    on_match=self._handle_anime_match, db_matches=db_matches,
                    user_id=self.dosya.ayarlar.get('user_id'), anime_name=anime_name
                )

                # Bölüm bulunduğunda koşullu butonu gizle
                if hasattr(self, 'btnCustomSearch'):
                    try:
                        self.btnCustomSearch.pack_forget()
                    except:
                        pass
                        
                # UI güncellemesi için update_idletasks kullan
                self.update_idletasks()
                with open("debug.log", "a") as f:
                    f.write("DEBUG: create_accordion tamamlandı\n")
                
            except Exception as e:
                with open("debug.log", "a") as f:
                    f.write(f"ERROR: create_accordion hatası: {str(e)}\n")
                print(f"Accordion oluşturma hatası: {e}")
                # Hata durumunda loading label'ını güncelle
                try:
                    loading_label.configure(text=f"Hata: {e}", text_color="#ff6b6b")
                except:
                    pass

        # Kısa bir bekleme sonrası accordion'u oluştur (performans için)
        self.after(50, create_accordion)  # Bu çağrı render_sources_page içinde yapılıyor

        with open("debug.log", "a") as f:
            f.write("DEBUG: render_sources_page tamamlandı\n")

    def _handle_anime_match(self, selected_anime):
        """Anime eşleştirmesini işle ve DB'ye kaydet."""
        try:
            print("DEBUG: _handle_anime_match başladı")
            # Geçerli seçimleri kontrol et
            valid_selections = {}
            for source, anime_title in selected_anime.items():
                if anime_title and anime_title not in ["Arama yapın...", "Sonuç bulunamadı", "Arama hatası"]:
                    # DB'den gelen eşleşmeler için prefix'i kaldır
                    clean_title = anime_title.replace("📚 ", "") if anime_title.startswith("📚 ") else anime_title
                    valid_selections[source] = clean_title

            print(f"DEBUG: selected_anime = {selected_anime}")
            print(f"DEBUG: valid_selections = {valid_selections}")
            print(f"DEBUG: len(valid_selections) = {len(valid_selections)}")

            if not valid_selections or len(valid_selections) < 2:
                self.message("Tüm kaynaklardan geçerli anime seçmelisiniz!", error=True)
                return

            # Eşleşen anime'leri DB'ye kaydet
            from turkanime_api.common.db import api_manager
            
            saved_count = 0
            for source, anime_title in selected_anime.items():
                try:
                    # Anime ID'sini bul (mevcut anime'den)
                    anime_id = None
                    if source in self.all_episodes and self.all_episodes[source]:
                        # İlk bölümün objesinden anime ID'sini al
                        first_episode = self.all_episodes[source][0]
                        if hasattr(first_episode['obj'], 'anime'):
                            anime_id = first_episode['obj'].anime.slug
                    
                    if anime_id:
                        success = api_manager.save_anime_match(source, str(anime_id), anime_title)
                        if success:
                            saved_count += 1
                except Exception as e:
                    print(f"{source} eşleştirme hatası: {e}")

            if saved_count > 0:
                self.message(f"{saved_count} kaynak eşleştirildi ve kaydedildi!", error=False)

                # Anime adını güncelle (eğer farklıysa)
                if hasattr(self, 'selected_anime') and self.selected_anime:
                    # Tüm kaynaklardan aynı anime adını kullan (ilk geçerli olanı)
                    correct_anime_name = None
                    for source, anime_title in valid_selections.items():
                        if anime_title and anime_title not in ["Arama yapın...", "Sonuç bulunamadı", "Arama hatası"]:
                            correct_anime_name = anime_title
                            break

                    if correct_anime_name:
                        # Mevcut anime adını kontrol et ve güncelle
                        current_name = self.selected_anime.get('title', {}).get('romaji', '') or \
                                     self.selected_anime.get('title', {}).get('english', '') or \
                                     self.selected_anime.get('title', {}).get('native', '')

                        if current_name != correct_anime_name:
                            print(f"Anime adı güncellendi: {current_name} -> {correct_anime_name}")
                            # Anime adını güncelle (title alanını değiştir)
                            if 'title' not in self.selected_anime:
                                self.selected_anime['title'] = {}
                            self.selected_anime['title']['romaji'] = correct_anime_name
                            self.selected_anime['title']['english'] = correct_anime_name
                            self.selected_anime['title']['native'] = correct_anime_name
            else:
                self.message("Eşleştirme kaydedilemedi!", error=True)
        except Exception as e:
            print(f"DEBUG: _handle_anime_match exception: {e}")
            import traceback
            traceback.print_exc()
            self.message(f"Eşleştirme hatası: {e}", error=True)

    def _load_anime_matches_from_db(self, anime_title: str) -> Dict[str, Dict]:
        """DB'den anime eşleşmelerini yükle."""
        from turkanime_api.common.db import api_manager
        
        matches = {}
        try:
            # Tüm eşleşmeleri al (şimdilik basit yaklaşım)
            # Gerçek uygulamada anime_title ile filtreleme yapılabilir
            all_matches = api_manager.get_anime_matches()
            
            for match in all_matches:
                source = match['source']
                # Basit eşleştirme: anime_title ile karşılaştır
                if anime_title.lower() in match['anime_title'].lower():
                    matches[source] = {
                        'anime_id': match['anime_id'],
                        'anime_title': match['anime_title']
                    }
        except Exception as e:
            print(f"DB eşleşme yükleme hatası: {e}")
        
        return matches

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
        """Yeni arama penceresi aç ve anime eşleştir.""" 
        if not hasattr(self, 'selected_anime') or not self.selected_anime:
            self.message("Önce bir anime seçin", error=True)
            return

        # Mevcut anime bilgilerini al
        anime_data = self.selected_anime
        romaji = anime_data.get('title', {}).get('romaji') or ""
        english = anime_data.get('title', {}).get('english') or ""
        original_title = romaji if romaji else english

        # Discord Rich Presence güncelle
        self.update_discord_presence(f"'{original_title}' arıyor", "TürkAnimu GUI")

        # AniList'te ara
        self.message("AniList'te aranıyor…")

        def search_worker():
            try:
                results = anilist_client.search_anime(original_title)
                self.after(0, lambda: self.display_anilist_search_results(results, f"AniList Arama: {original_title}"))
            except Exception as e:
                self.after(0, lambda: self.message(f"AniList arama hatası: {e}", error=True))

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

        # Başlık selector'ünü güncelle
        self.update_title_selector()

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

        trending_title = ctk.CTkLabel(title_frame, text="🔥 Bu Hafta Trend",
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

    def _update_loading_status(self, message):
        """Loading durumunu güncelle."""
        if hasattr(self, 'status_label'):
            self.status_label.configure(text=message, text_color="#cccccc")

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

        # Seçilen başlıktan başlık kısmını al
        selected_title = ""
        if hasattr(self, 'cmbTitle') and hasattr(self, 'selected_title'):
            selected_title = getattr(self, 'selected_title', "")
            if selected_title:
                # "🇺🇸 İngilizce: " veya "🇯🇵 Romanji: " kısmını çıkar
                if "İngilizce: " in selected_title:
                    selected_title = selected_title.split("İngilizce: ")[1]
                elif "Romanji: " in selected_title:
                    selected_title = selected_title.split("Romanji: ")[1]
                elif "Orijinal: " in selected_title:
                    selected_title = selected_title.split("Orijinal: ")[1]
                else:
                    selected_title = ""

        # Başlık seçimi varsa onu kullan, yoksa normal arama yap
        search_query = selected_title if selected_title else query

        # Discord Rich Presence güncelle
        self.update_discord_presence(f"'{search_query}' arıyor", "TürkAnimu GUI")

        # AniList'te ara
        self.message("AniList'te aranıyor…")

        def search_worker():
            try:
                results = anilist_client.search_anime(search_query)
                self.after(0, lambda: self.display_anilist_search_results(results, f"AniList Arama: {search_query}"))
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