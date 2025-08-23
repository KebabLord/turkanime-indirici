from __future__ import annotations

from typing import List
import sys
import os
import concurrent.futures as cf
from PyQt6 import QtCore, QtGui, QtWidgets

from turkanime_api.objects import Anime, Bolum
from turkanime_api.bypass import fetch
from turkanime_api.cli.dosyalar import Dosyalar
from turkanime_api.cli.cli_tools import VidSearchCLI, indir_aria2c
from turkanime_api.cli.gereksinimler import Gereksinimler


class WorkerSignals(QtCore.QObject):
    progress = QtCore.pyqtSignal(str)          # Genel durum metni
    progress_item = QtCore.pyqtSignal(object)  # {slug,title,status,downloaded,total,percent,speed,eta}
    error = QtCore.pyqtSignal(str)             # Genel hata
    error_item = QtCore.pyqtSignal(object)     # {slug,title,error}
    success = QtCore.pyqtSignal()
    found = QtCore.pyqtSignal(object)


class DownloadWorker(QtCore.QRunnable):
    """Qt thread pool içinde indirme işini çalıştırır."""

    def __init__(self, bolumler: List[Bolum]):
        super().__init__()
        self.bolumler = bolumler
        self.signals = WorkerSignals()

    @QtCore.pyqtSlot()
    def run(self):
        try:
            dosya = Dosyalar()
            paralel = dosya.ayarlar.get("paralel indirme sayisi", 2)

            def dl_one(bolum: Bolum):
                self.signals.progress.emit(f"{bolum.slug} için video aranıyor…")
                self.signals.progress_item.emit({
                    "slug": bolum.slug,
                    "title": bolum.title,
                    "status": "hazır",
                    "downloaded": 0,
                    "total": None,
                    "percent": 0,
                    "speed": None,
                    "eta": None,
                })
                best_video = bolum.best_video(by_res=dosya.ayarlar.get("max resolution", True))
                if not best_video:
                    self.signals.error_item.emit({
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
                            self.signals.progress.emit(f"{bolum.slug}: {int(cur/1024/1024)}/{int(tot/1024/1024)} MB")
                        else:
                            self.signals.progress.emit(f"{bolum.slug}: indiriliyor…")
                    elif st == "finished":
                        self.signals.progress.emit(f"{bolum.slug}: indirildi")

                    # Tablo güncellemesi
                    self.signals.progress_item.emit({
                        "slug": bolum.slug,
                        "title": bolum.title,
                        "status": ("indiriliyor" if st == "downloading" else "indirildi" if st == "finished" else st),
                        "downloaded": cur,
                        "total": tot,
                        "percent": pct,
                        "speed": spd,
                        "eta": eta,
                    })

                if best_video.player != "ALUCARD(BETA)" and dosya.ayarlar.get("aria2c kullan"):
                    indir_aria2c(best_video, callback=hook, output=down_dir)
                else:
                    best_video.indir(callback=hook, output=down_dir)
                dosya.set_gecmis(bolum.anime.slug, bolum.slug, "indirildi")
                # Tamamlandı sinyali
                self.signals.progress_item.emit({
                    "slug": bolum.slug,
                    "title": bolum.title,
                    "status": "tamamlandı",
                    "downloaded": last.get("b"),
                    "total": last.get("b"),
                    "percent": 100,
                    "speed": None,
                    "eta": 0,
                })

            with cf.ThreadPoolExecutor(max_workers=paralel) as executor:
                futures = [executor.submit(dl_one, b) for b in self.bolumler]
                for fut in cf.as_completed(futures):
                    fut.result()
            self.signals.success.emit()
        except Exception as e:
            self.signals.error.emit(str(e))


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


class VideoFindWorker(QtCore.QRunnable):
    """Bölüm için en uygun videoyu bulur ve sonucu döndürür."""

    def __init__(self, bolum: Bolum):
        super().__init__()
        self.bolum = bolum
        self.signals = WorkerSignals()

    @QtCore.pyqtSlot()
    def run(self):
        try:
            dosya = Dosyalar()
            vid_cli = VidSearchCLI()
            best = self.bolum.best_video(
                by_res=dosya.ayarlar.get("max resolution", True),
                callback=vid_cli.callback,
            )
            if not best:
                self.signals.error.emit("Uygun video bulunamadı")
                return
            self.signals.progress.emit("Video bulundu")
            self.signals.success.emit()
            self.signals.found.emit(best)
        except Exception as e:
            self.signals.error.emit(str(e))


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TürkAnimu")
        self.resize(1100, 720)

        # App icon
        try:
            icon_path = _resource_path(os.path.join('docs', 'TurkAnimu.ico'))
            if os.path.exists(icon_path):
                self.setWindowIcon(QtGui.QIcon(icon_path))
        except Exception:
            pass

        self.pool = QtCore.QThreadPool.globalInstance()
        self.dosya = Dosyalar()
        # Ana widget -> TabWidget
        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        # Keşfet sekmesi
        page_main = QtWidgets.QWidget()
        main = QtWidgets.QVBoxLayout(page_main)

        # Üst: arama ve aksiyonlar
        top_bar = QtWidgets.QHBoxLayout()
        self.searchEdit = QtWidgets.QLineEdit()
        self.searchEdit.setPlaceholderText("Anime ara…")
        self.btnSearch = QtWidgets.QPushButton("Ara")
        self.btnSettings = QtWidgets.QPushButton("Ayarlar")
        top_bar.addWidget(self.searchEdit, 1)
        top_bar.addWidget(self.btnSearch)
        top_bar.addWidget(self.btnSettings)
        main.addLayout(top_bar)

        # Orta: listeler
        splitter = QtWidgets.QSplitter()
        splitter.setOrientation(QtCore.Qt.Orientation.Horizontal)

        # Anime listesi
        self.lstAnime = QtWidgets.QListWidget()
        self.lstAnime.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.lstAnime.setAlternatingRowColors(True)
        self.lstAnime.setStyleSheet("QListWidget{font-size:14px}")
        splitter.addWidget(self.lstAnime)

        # Bölüm listesi
        self.lstBolum = QtWidgets.QListWidget()
        self.lstBolum.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lstBolum.setAlternatingRowColors(True)
        self.lstBolum.setStyleSheet("QListWidget{font-size:14px}")
        splitter.addWidget(self.lstBolum)

        splitter.setSizes([350, 750])
        main.addWidget(splitter, 1)

        # Alt: eylem düğmeleri
        actions = QtWidgets.QHBoxLayout()
        self.btnPlay = QtWidgets.QPushButton("İzle")
        self.btnDownload = QtWidgets.QPushButton("İndir")
        actions.addWidget(self.btnPlay)
        actions.addWidget(self.btnDownload)
        main.addLayout(actions)

        # Durum çubuğu
        self.status = QtWidgets.QStatusBar()
        self.setStatusBar(self.status)

        self.tabs.addTab(page_main, "Keşfet")

        # İndirmeler sekmesi
        page_dl = QtWidgets.QWidget()
        dl_layout = QtWidgets.QVBoxLayout(page_dl)
        self.tblDownloads = QtWidgets.QTableWidget(0, 6)
        self.tblDownloads.setHorizontalHeaderLabels(["Bölüm", "Durum", "%", "Boyut", "Hız", "Kalan"])
        self.tblDownloads.horizontalHeader().setStretchLastSection(True)
        self.tblDownloads.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        dl_layout.addWidget(self.tblDownloads)
        self.txtLog = QtWidgets.QTextEdit()
        self.txtLog.setReadOnly(True)
        self.txtLog.setPlaceholderText("İndirme ve hata günlükleri burada görünecek…")
        dl_layout.addWidget(self.txtLog)
        self.tabs.addTab(page_dl, "İndirmeler")

        # İndirme satır indeksleri
        self._dl_rows = {}  # slug -> row index

        # Sinyaller
        self.btnSearch.clicked.connect(self.on_search)
        self.searchEdit.returnPressed.connect(self.on_search)
        self.lstAnime.itemSelectionChanged.connect(self.on_anime_selected)
        self.btnPlay.clicked.connect(self.on_play_selected)
        self.btnDownload.clicked.connect(self.on_download_selected)
        self.btnSettings.clicked.connect(self.on_open_settings)

        # Başlarken gereksinimleri kontrol et (bloklamasın diye iş parçacığında çalıştır)
        QtCore.QTimer.singleShot(100, self.check_requirements_async)
        # Bypass oturum ısındır
        def _warm():
            try:
                fetch(None)
            except Exception:
                pass
        cf.ThreadPoolExecutor(max_workers=1).submit(_warm)

    # --- İşlevler ---
    def message(self, text: str, error: bool = False):
        self.status.showMessage(text, 5000)
        if error:
            QtWidgets.QMessageBox.warning(self, "Hata", text)

    def check_requirements_async(self):
        def _run():
            try:
                gerek = Gereksinimler()
                eksikler = gerek.eksikler
                if not eksikler:
                    return None
                # Windows’ta otomatik indir, diğerlerinde sadece bilgi ver.
                import os
                if os.name == "nt":
                    links = gerek.url_liste
                    fails = gerek.otomatik_indir(url_liste=links)
                    if fails:
                        return "Bazı gereksinimler kurulamadı: " + ", ".join([f["name"] for f in fails])
                    return None
                else:
                    return "Gereksinimler eksik; lütfen README’deki yönergelerle kurun."
            except Exception as e:
                return str(e)

        pool = cf.ThreadPoolExecutor(max_workers=1)
        fut = pool.submit(_run)

        def _done(_):
            err = fut.result()
            if err:
                self.message(err, error=True)
            else:
                self.message("Gereksinimler hazır")
        fut.add_done_callback(_done)

    def on_search(self):
        query = self.searchEdit.text().strip().lower()
        if not query:
            return
        self.message("Anime listesi getiriliyor…")

        def _load():
            return Anime.get_anime_listesi()

        pool = cf.ThreadPoolExecutor(max_workers=1)
        fut = pool.submit(_load)

        def _done(_):
            try:
                all_list = fut.result()
            except Exception as e:
                self.message(str(e), error=True)
                return
            self.lstAnime.clear()
            for slug, name in all_list:
                if query in name.lower():
                    item = QtWidgets.QListWidgetItem(name)
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, slug)
                    self.lstAnime.addItem(item)
            if self.lstAnime.count() == 0:
                self.message("Sonuç bulunamadı")
            else:
                self.message(f"{self.lstAnime.count()} sonuç")
        fut.add_done_callback(_done)

    def on_anime_selected(self):
        items = self.lstAnime.selectedItems()
        if not items:
            return
        slug = items[0].data(QtCore.Qt.ItemDataRole.UserRole)
        self.message("Bölümler yükleniyor…")

        def _load():
            anime = Anime(slug)
            return anime.bolumler

        pool = cf.ThreadPoolExecutor(max_workers=1)
        fut = pool.submit(_load)

        def _done(_):
            try:
                bolumler = fut.result()
            except Exception as e:
                self.message(str(e), error=True)
                return
            self.lstBolum.clear()
            dosya = Dosyalar()
            gecmis = dosya.gecmis
            izlenen = gecmis.get("izlendi", {})
            indirilen = gecmis.get("indirildi", {})
            anime_slug = bolumler[0].anime.slug if bolumler else ""
            for bol in bolumler:
                text = bol.title
                marks = []
                if anime_slug in izlenen and bol.slug in izlenen[anime_slug]:
                    marks.append("●")
                if anime_slug in indirilen and bol.slug in indirilen[anime_slug]:
                    marks.append("↓")
                if marks:
                    text += "  " + " ".join(marks)
                item = QtWidgets.QListWidgetItem(text)
                item.setData(QtCore.Qt.ItemDataRole.UserRole, bol)
                self.lstBolum.addItem(item)
            self.message(f"{self.lstBolum.count()} bölüm yüklendi")
        fut.add_done_callback(_done)

    def _get_selected_bolumler(self) -> List[Bolum]:
        return [i.data(QtCore.Qt.ItemDataRole.UserRole) for i in self.lstBolum.selectedItems()]

    def on_play_selected(self):
        sel = self._get_selected_bolumler()
        if not sel:
            self.message("Bölüm seçin", error=True)
            return
        bolum = sel[0]
        self.message("En iyi video aranıyor…")
        worker = VideoFindWorker(bolum)
        worker.signals.error.connect(lambda m: self.message(m, error=True))
        worker.signals.found.connect(self._play_video)
        self.pool.start(worker)

    def _play_video(self, video):
        dosya = Dosyalar()
        proc = video.oynat(
            dakika_hatirla=dosya.ayarlar.get("dakika hatirla", True),
            izlerken_kaydet=dosya.ayarlar.get("izlerken kaydet", False),
        )
        if proc.returncode == 0:
            self.message("Oynatma tamamlandı")
            dosya.set_gecmis(video.bolum.anime.slug, video.bolum.slug, "izlendi")
        else:
            self.message("Video çalışmadı", error=True)

    def on_download_selected(self):
        sel = self._get_selected_bolumler()
        if not sel:
            self.message("En az bir bölüm seçin", error=True)
            return
        # İndirmeler tablosuna satırları ekle
        for bolum in sel:
            self._ensure_dl_row(bolum)
        self.message("İndirme başlıyor…")
        # İndirmeler sekmesine geç
        try:
            idx = self.tabs.indexOf(self.tblDownloads.parentWidget())
            if idx != -1:
                self.tabs.setCurrentIndex(idx)
        except Exception:
            pass
        worker = DownloadWorker(sel)
        worker.signals.error.connect(lambda m: (self._append_log(f"[HATA] {m}"), self.message(m, error=True)))
        worker.signals.success.connect(lambda: self.message("İndirme tamamlandı"))
        worker.signals.progress.connect(self._append_log)
        worker.signals.progress_item.connect(self._on_progress_item)
        worker.signals.error_item.connect(self._on_error_item)
        self.pool.start(worker)

    def on_open_settings(self):
        d = SettingsDialog(self)
        d.exec()

    # --- İndirme tablosu yardımcıları ---
    def _ensure_dl_row(self, bolum: Bolum):
        slug = bolum.slug
        if slug in self._dl_rows:
            return self._dl_rows[slug]
        row = self.tblDownloads.rowCount()
        self.tblDownloads.insertRow(row)
        self.tblDownloads.setItem(row, 0, QtWidgets.QTableWidgetItem(bolum.title))
        self.tblDownloads.setItem(row, 1, QtWidgets.QTableWidgetItem("hazır"))
        self.tblDownloads.setItem(row, 2, QtWidgets.QTableWidgetItem("0"))
        self.tblDownloads.setItem(row, 3, QtWidgets.QTableWidgetItem("0 / ? MB"))
        self.tblDownloads.setItem(row, 4, QtWidgets.QTableWidgetItem("-"))
        self.tblDownloads.setItem(row, 5, QtWidgets.QTableWidgetItem("-"))
        self._dl_rows[slug] = row
        return row

    @QtCore.pyqtSlot(object)
    def _on_progress_item(self, data: object):
        try:
            slug = data.get("slug")
            title = data.get("title")
            status = data.get("status")
            cur = data.get("downloaded")
            tot = data.get("total")
            pct = data.get("percent")
            spd = data.get("speed")
            eta = data.get("eta")
            if slug not in self._dl_rows:
                # Beklenmedikse satır ekle
                row = self.tblDownloads.rowCount()
                self.tblDownloads.insertRow(row)
                self.tblDownloads.setItem(row, 0, QtWidgets.QTableWidgetItem(title or slug))
                self._dl_rows[slug] = row
            row = self._dl_rows[slug]
            # Durum
            if status:
                self.tblDownloads.item(row, 1).setText(str(status))
            # Yüzde
            if pct is not None:
                self.tblDownloads.item(row, 2).setText(str(pct))
            # Boyut
            def mb(x):
                return int(x/1024/1024) if isinstance(x,(int,float)) else None
            size_text = ""
            mcur, mtot = mb(cur), mb(tot)
            if mcur is not None and mtot is not None:
                size_text = f"{mcur} / {mtot} MB"
            elif mcur is not None:
                size_text = f"{mcur} MB"
            elif mtot is not None:
                size_text = f"0 / {mtot} MB"
            if size_text:
                self.tblDownloads.item(row, 3).setText(size_text)
            # Hız
            if spd is not None:
                try:
                    spd_txt = f"{spd/1024/1024:.2f} MB/s"
                except Exception:
                    spd_txt = "-"
                self.tblDownloads.item(row, 4).setText(spd_txt)
            # Kalan
            if eta is not None:
                try:
                    m, s = divmod(int(eta), 60)
                    h, m = divmod(m, 60)
                    eta_txt = f"{h:02d}:{m:02d}:{s:02d}"
                except Exception:
                    eta_txt = "-"
                self.tblDownloads.item(row, 5).setText(eta_txt)
            # Tamamlandı boya
            if status in ("tamamlandı", "indirildi"):
                for c in range(6):
                    it = self.tblDownloads.item(row, c)
                    if it:
                        it.setBackground(QtGui.QColor(30, 60, 30))
        except Exception as e:
            self.txtLog.append(f"Hata (progress render): {e}")

    @QtCore.pyqtSlot(object)
    def _on_error_item(self, data: object):
        slug = data.get("slug")
        title = data.get("title")
        err = data.get("error")
        self.txtLog.append(f"[HATA] {title or slug}: {err}")

    def _append_log(self, line: str):
        try:
            self.txtLog.append(line)
        except Exception:
            pass


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayarlar")
        self.resize(420, 360)
        layout = QtWidgets.QFormLayout(self)

        self.dosya = Dosyalar()
        a = self.dosya.ayarlar

        self.chkManuel = QtWidgets.QCheckBox()
        self.chkManuel.setChecked(a.get("manuel fansub", False))

        self.chkSaveWhileWatch = QtWidgets.QCheckBox()
        self.chkSaveWhileWatch.setChecked(a.get("izlerken kaydet", False))

        self.chkWatchedIcon = QtWidgets.QCheckBox()
        self.chkWatchedIcon.setChecked(a.get("izlendi ikonu", True))

        self.spinParallel = QtWidgets.QSpinBox()
        self.spinParallel.setRange(1, 8)
        self.spinParallel.setValue(a.get("paralel indirme sayisi", 3))

        self.chkMaxRes = QtWidgets.QCheckBox()
        self.chkMaxRes.setChecked(a.get("max resolution", True))

        self.chkRememberMin = QtWidgets.QCheckBox()
        self.chkRememberMin.setChecked(a.get("dakika hatirla", True))

        self.chkAria2 = QtWidgets.QCheckBox()
        self.chkAria2.setChecked(a.get("aria2c kullan", False))

        self.txtDownloads = QtWidgets.QLineEdit(a.get("indirilenler", "."))
        btnBrowse = QtWidgets.QPushButton("Seç…")
        btnRow = QtWidgets.QHBoxLayout()
        btnRow.addWidget(self.txtDownloads, 1)
        btnRow.addWidget(btnBrowse)
        wRow = QtWidgets.QWidget()
        wRow.setLayout(btnRow)

        layout.addRow("İndirilenler klasörü:", wRow)
        layout.addRow("İzlerken kaydet:", self.chkSaveWhileWatch)
        layout.addRow("Manuel fansub seçimi:", self.chkManuel)
        layout.addRow("İzlendi/İndirildi ikonu:", self.chkWatchedIcon)
        layout.addRow("Paralel indirme sayısı:", self.spinParallel)
        layout.addRow("Maksimum çözünürlük:", self.chkMaxRes)
        layout.addRow("Kaldığın dakikayı hatırla:", self.chkRememberMin)
        layout.addRow("Aria2c kullan:", self.chkAria2)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addRow(btns)

        btns.accepted.connect(self.on_save)
        btns.rejected.connect(self.reject)
        btnBrowse.clicked.connect(self.on_choose_dir)

    def on_choose_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "İndirilenler klasörünü seç")
        if d:
            self.txtDownloads.setText(d)

    def on_save(self):
        self.dosya.set_ayar("manuel fansub", self.chkManuel.isChecked())
        self.dosya.set_ayar("izlerken kaydet", self.chkSaveWhileWatch.isChecked())
        self.dosya.set_ayar("izlendi ikonu", self.chkWatchedIcon.isChecked())
        self.dosya.set_ayar("paralel indirme sayisi", int(self.spinParallel.value()))
        self.dosya.set_ayar("max resolution", self.chkMaxRes.isChecked())
        self.dosya.set_ayar("dakika hatirla", self.chkRememberMin.isChecked())
        self.dosya.set_ayar("aria2c kullan", self.chkAria2.isChecked())
        self.dosya.set_ayar("indirilenler", self.txtDownloads.text())
        self.accept()


def run():
    # PATH'e uygulama dizinini ekle (mpv, yt-dlp, aria2c için)
    sep = ";" if os.name == "nt" else ":"
    path_parts = [os.environ.get("PATH", "")]
    # Kullanıcı app verisi
    path_parts.append(Dosyalar().ta_path)
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

    app = QtWidgets.QApplication(sys.argv)
    # Uygulama simgesi (genel)
    try:
        _icon_path = _resource_path(os.path.join('docs', 'TurkAnimu.ico'))
        if os.path.exists(_icon_path):
            app.setWindowIcon(QtGui.QIcon(_icon_path))
    except Exception:
        pass
    # Tutarlı, modern bir görünüm
    app.setStyle("Fusion")
    palette = app.palette()
    palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(30, 30, 30))
    palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(230, 230, 230))
    palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(45, 45, 45))
    palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(36, 36, 36))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor(255, 255, 220))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor(0, 0, 0))
    palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(220, 220, 220))
    palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(45, 45, 45))
    palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(220, 220, 220))
    palette.setColor(QtGui.QPalette.ColorRole.BrightText, QtGui.QColor(255, 0, 0))
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(64, 128, 255))
    palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor(255, 255, 255))
    app.setPalette(palette)

    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
