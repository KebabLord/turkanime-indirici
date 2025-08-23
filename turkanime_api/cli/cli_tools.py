from os import name,system,path,listdir
from tempfile import NamedTemporaryFile
import re
from time import sleep
from threading import Thread
from prompt_toolkit import styles

from rich.panel import Panel
from rich.console import Group
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    SpinnerColumn,
    DownloadColumn,
    TimeRemainingColumn,
    TaskProgressColumn,
    TransferSpeedColumn
)

def clear():
    """ Daha kompakt görüntü için her prompt sonrası clear
        Debug yapacaksanız devre dışı bırakmanız önerilir.
    """
    system('cls' if name == 'nt' else 'clear')

def CliStatus(msg,hide=True):
    prg = Progress(
        SpinnerColumn("bouncingBar"),
        TextColumn("[cyan]"+msg),
        BarColumn(bar_width=40),
        transient=hide)
    prg.add_task(msg, total=None)
    return prg

class DownloadCLI():
    def __init__(self):
        columns = (
            SpinnerColumn("bouncingBar"), '[cyan]{task.description}',
            BarColumn(bar_width=40), TaskProgressColumn(), DownloadColumn(),
            TransferSpeedColumn(), TimeRemainingColumn()
        )
        self.progress = Progress(*columns)
        self.multi_tasks = {}
    def ytdl_callback(self,hook):
        """ ydl_options['progress_hooks'] için callback handler. """
        if hook["status"] in ("finished","downloading"):
            descp = "İndiriliyor.."
            total = hook.get("total_bytes") or hook.get("total_bytes_estimate")
            completed = hook.get("downloaded_bytes")
            if not self.progress.tasks:
                task_id = self.progress.add_task(descp, total=total)
            else:
                task_id = self.progress.tasks[0].id
            if hook["status"] == "finished":
                task = self.progress.tasks[0]
                dom = (completed or total) or (task.total or task.completed) # Dominant valid value
                self.progress.update(task_id, description="İndirildi.",completed=dom, total=dom)
            elif completed:
                if total and completed >= total:
                    descp = "İndirildi!"
                self.progress.update(task_id,
                    description=descp,
                    completed=completed,
                    total=total)
        if hook["status"] == "error":
            # aria2c fallback veya hata mesajını bir kerelik yaz
            msg = hook.get("message")
            if msg:
                try:
                    from rich import print as rprint
                    rprint(f"[red]Hata:[/red] {msg}")
                except Exception:
                    pass
            if self.progress.tasks:
                # TODO: hata mesajı gösterilmeli
                self.progress.tasks.pop(0)
    def dl_callback(self,hook):
        """ gereksinimler.dosya_indir için callback handler. """
        if not self.multi_tasks or hook.get("file") not in self.multi_tasks:
            task_id = self.progress.add_task(hook.get("file"), total=hook.get("total"))
            self.multi_tasks[hook.get("file")] = task_id
        else:
            task_id = self.multi_tasks[hook.get("file")]
        self.progress.update(task_id,completed=hook.get("current"))

class VidSearchCLI():
    def __init__(self):
        columns = (
            SpinnerColumn("bouncingBar"),
            '[cyan]{task.description}',
            BarColumn(bar_width=40),
            TextColumn("[cyan]{task.completed}/{task.total} denendi."),
        )
        self.progress = Progress(*columns)
    def callback(self, hook):
        """ Objects.Video.best_video methodu için callback handler. """
        msg = ""
        if hook.get("player"):
            msg += f'{hook["player"]} {hook["status"]}'
            msg += "!" if hook["status"] == "çalışıyor" else "."
        elif hook.get("status") == "hiçbiri çalışmıyor":
            pass # TODO: hata mesajı gösterilmeli
        if self.progress.tasks:
            task_id = self.progress.tasks[0].id
        else:
            task_id = self.progress.add_task(msg, total=hook["total"])
        completed = hook["total"] if hook["status"] == "çalışıyor" else hook["current"]
        self.progress.update(task_id, completed=completed, description=msg)


def indirme_task_cli(bolum,table,dosya):
    """ Progress barı dinamik olarak güncellerken indirme yapar. """
    vid_cli = VidSearchCLI()
    dl_cli = DownloadCLI()
    table.add_row(Panel.fit(
            Group(vid_cli.progress, dl_cli.progress),
            title=bolum.slug,
            border_style="green"))
    table.add_row("")
    # En iyi çalışan videoyu bul.
    best_video = bolum.best_video(
        by_res=dosya.ayarlar["max resolution"],
        callback=vid_cli.callback)
    if not best_video:
        # TODO: hata mesajı gösterilmeli
        return
    down_dir = dosya.ayarlar["indirilenler"]
    success = False
    try:
        if best_video.player != "ALUCARD(BETA)" and dosya.ayarlar.get("aria2c kullan"):
            # Aria2C Hızlandırıcı ile indir (fallback içerir)
            success = bool(indir_aria2c(best_video, callback=dl_cli.ytdl_callback, output=down_dir))
        else:
            # Yt-dlp ile İndir
            best_video.indir(callback=dl_cli.ytdl_callback, output=down_dir)
            success = True
    except Exception:
        success = False
    if success:
        dosya.set_gecmis(bolum.anime.slug, bolum.slug, "indirildi")


def indir_aria2c(video, callback, output):
    """ Objects.Video.indir için aria2c implementasyonu
    Harici downloader kullanınca ytdl hooklar çalışmadığından
    custom_hook fonksiyonunu bu şekilde yazmak zorunda kaldım
    """
    subdir = path.join(output,(video.bolum.anime.slug if video.bolum.anime else ""))
    tmp = NamedTemporaryFile(delete=False)
    # aria2c mevcut mu? yoksa direkt yt-dlp ile indir
    try:
        from shutil import which as _which
        if not _which('aria2c'):
            video.indir(callback, output)
            return True
    except Exception:
        video.indir(callback, output)
        return True

    old_opts = dict(video.ydl_opts)
    video.ydl_opts = {
        **video.ydl_opts,
        'external_downloader' : {'default': 'aria2c'},
        'external_downloader_args': {'aria2c': [
            '--quiet',
            '--file-allocation=none',
            '--allow-overwrite=true',
            '--auto-file-renaming=false',
            '--check-certificate=false',
            '--min-split-size=1M',
            '--max-connection-per-server=16',
            '--summary-interval=0',
            '--log='+tmp.name,
            '--log-level=info']}
    }
    is_finished = False
    def custom_hook():
        """ Toplam boyutu loglardan, indirileni de dosya boyutundan öğren ve callback yolla. """
        total = None
        while not is_finished:
            sleep(1)
            # Try to get estimated file size from aria2c log.
            try:
                with open(tmp.name,encoding="utf-8") as fp:
                    log = fp.read()
                sizes = re.findall(r'Content-Type: video.*\n?Content-Length: (\d+)',log)
                total = max([int(i) for i in sizes])
            except ValueError:
                pass
            # Calculate downloaded bytes from part files.
            downloaded = 0
            try:
                slug = re.escape(video.bolum.slug)
                for file in listdir(subdir):
                    # slug ile başlayan gerçek çıktı veya parça dosyaları
                    if not re.match(rf"^{slug}\." , file):
                        continue
                    if file.endswith('.aria2'):
                        # aria2 kontrol dosyası, boyuta eklenmez
                        continue
                    downloaded += path.getsize(path.join(subdir, file))
            except FileNotFoundError:
                continue
            if not total and not downloaded:
                continue
            if total is not None and downloaded > total:
                total = None
            callback({
                "status": "downloading",
                "downloaded_bytes": downloaded,
                "total_bytes": total})
    file_size_thread = Thread(target=custom_hook)
    file_size_thread.start()
    def _last_log_line():
        try:
            with open(tmp.name, encoding="utf-8", errors="ignore") as fp:
                lines = [ln.strip() for ln in fp.readlines()]
            for ln in reversed(lines):
                if ln:
                    return ln
        except Exception:
            pass
        return None

    ok = False
    try:
        video.indir(callback, output)
        ok = True
    except Exception as _e:
        # aria2c başarısız olduysa fallback: yt-dlp ile indir
        is_finished = True
        file_size_thread.join()
        last_ln = _last_log_line()
        try:
            payload = {"status": "error"}
            if last_ln:
                payload["message"] = last_ln
            callback(payload)
        except Exception:
            pass
        # external_downloader ayarlarını kaldır
        video.ydl_opts = old_opts
        # Yeniden indir (yt-dlp native)
        try:
            video.indir(callback, output)
            ok = True
        except Exception:
            ok = False
    else:
        is_finished = True
        file_size_thread.join()
        callback({"status": "finished"})
        ok = True
    finally:
        del tmp
    return ok


prompt_tema = styles.Style([
    ('qmark', 'fg:#5F819D bold'),
    ('question', 'fg:#289c64 bold'),
    ('answer', 'fg:#48b5b5 bg:#hidden bold'),
    ('pointer', 'fg:#48b5b5 bold'),
    ('highlighted', 'fg:#07d1e8'),
    ('selected', 'fg:#48b5b5 bg:black bold'),
    ('separator', 'fg:#6C6C6C'),
    ('instruction', 'fg:#77a371'),
    ('text', ''),
    ('disabled', 'fg:#858585 italic'),
])
