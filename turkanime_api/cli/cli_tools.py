from os import name,system,path,listdir
from tempfile import NamedTemporaryFile
import re
from time import sleep
from threading import Thread,Lock
from collections import OrderedDict
from prompt_toolkit import styles
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl

from rich.panel import Panel
from rich.console import Console,Group
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

from ..objects import SUPPORTED

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

def player_onceligi(ayarlar):
    """ Kayıtlı player sırasını desteklenen player listesine göre temizler. """
    kayitli = ayarlar.get("player önceliği") if isinstance(ayarlar,dict) else None
    sirali = [p for p in (kayitli or []) if p in SUPPORTED]
    for i,player in enumerate(SUPPORTED):
        if player not in sirali:
            sirali.insert(min(i,len(sirali)),player)
    return sirali

def player_onceligi_uygula(ayarlar):
    """ Kayıtlı player önceliğini runtime'daki SUPPORTED listesine uygular. """
    SUPPORTED[:] = player_onceligi(ayarlar)

def player_onceligi_duzenle(players):
    """ Player önceliğini tek ekranda klavye ile sıralatır. """
    players, cursor, saved = players.copy(), 0, False
    def text():
        lines = [
            ("class:help", "↑/↓: seç   w/s: taşı   Enter: kaydet   Esc/q: çık\n\n"),
        ]
        for i,p in enumerate(players):
            style = "class:selected" if i == cursor else ""
            lines.append((style,f"{'>' if i == cursor else ' '} {i + 1:02}. {p}\n"))
        return lines
    def move_cursor(delta):
        nonlocal cursor
        cursor = max(0,min(len(players) - 1,cursor + delta))
    def move_item(delta):
        nonlocal cursor
        new = max(0,min(len(players) - 1,cursor + delta))
        if new != cursor:
            players[cursor],players[new] = players[new],players[cursor]
            cursor = new
    kb = KeyBindings()
    @kb.add("up")
    @kb.add("k")
    def _(event):
        move_cursor(-1)
    @kb.add("down")
    @kb.add("j")
    def _(event):
        move_cursor(1)
    @kb.add("w")
    @kb.add("u")
    def _(event):
        move_item(-1)
    @kb.add("s")
    @kb.add("d")
    def _(event):
        move_item(1)
    @kb.add("enter")
    def _(event):
        nonlocal saved
        saved = True
        event.app.exit()
    @kb.add("escape")
    @kb.add("q")
    def _(event):
        event.app.exit()
    Console().print(
        '[bold red]UYARI:[/bold red] "Max çözünürlüğe ulaş" ayarı etkinse ve '
        "öncelik verdiğiniz oynatıcı 1080p çözünürlüğü desteklemiyorsa, player göz ardı edilebilir."
    )
    print()
    app = Application(
        layout=Layout(Window(FormattedTextControl(text),always_hide_cursor=True)),
        key_bindings=kb,
        style=prompt_tema,
        full_screen=False,
        mouse_support=False)
    app.run()
    return players if saved else None

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

class DownloadBoard():
    def __init__(self):
        self.live = None
        self.active = OrderedDict()
        self.lock = Lock()

    def render(self):
        return Group(*self.active.values())

    def refresh(self):
        if self.live:
            self.live.update(self.render())

    def add(self, slug, renderable):
        with self.lock:
            self.active[slug] = Panel.fit(renderable,title=slug,border_style="green")
            self.refresh()

    def finish(self, slug, status="indirildi"):
        with self.lock:
            self.active.pop(slug,None)
            self.refresh()
            if self.live:
                if status == "indirildi":
                    self.live.console.print(f"[green]+[/green] [white]{slug}[/white] [green]{status}[/green]")
                else:
                    self.live.console.print(f"[red]![/red] [white]{slug}[/white] [red]{status}[/red]")

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


def indirme_task_cli(bolum,board,dosya,by_fansub=None):
    """ Progress barı dinamik olarak güncellerken indirme yapar. """
    vid_cli = VidSearchCLI()
    dl_cli = DownloadCLI()
    board.add(bolum.slug,Group(vid_cli.progress,dl_cli.progress))
    try:
        # En iyi çalışan videoyu bul.
        best_video = bolum.best_video(
            by_res=dosya.ayarlar["max resolution"],
            by_fansub=by_fansub,
            callback=vid_cli.callback)
        if not best_video:
            # TODO: hata mesajı gösterilmeli
            print("  (!) Hiçbir çalışan video bulunamadı.")
            board.finish(bolum.slug,"indirilemedi")
            return
        down_dir = dosya.ayarlar["indirilenler"]
        if best_video.player != "ALUCARD(BETA)" and dosya.ayarlar.get("aria2c kullan"):
            # Aria2C Hızlandırıcı İle Videoyu indir
            indir_aria2c(best_video, callback=dl_cli.ytdl_callback, output=down_dir)
        else:
            # Yt-dlp ile Videoyu indir
            best_video.indir(callback=dl_cli.ytdl_callback, output=down_dir)
        dosya.set_gecmis(bolum.anime.slug, bolum.slug, "indirildi")
        board.finish(bolum.slug)
    except Exception:
        board.finish(bolum.slug,"indirilemedi")
        raise


def indir_aria2c(video, callback, output):
    """ Objects.Video.indir için aria2c implementasyonu
    Harici downloader kullanınca ytdl hooklar çalışmadığından
    custom_hook fonksiyonunu bu şekilde yazmak zorunda kaldım
    """
    subdir = path.join(output,(video.bolum.anime.slug if video.bolum.anime else ""))
    tmp = NamedTemporaryFile(delete=False)
    video.ydl_opts = {
        **video.ydl_opts,
        'external_downloader' : {'default': 'aria2c'},
        'external_downloader_args': {'aria2c': [
            '--quiet','--file-allocation=none',
            '--log='+tmp.name,'--log-level=info']}
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
                for file in listdir(subdir):
                    if not re.search(video.bolum.slug+r".*part(-Frag\d+)?$",file):
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
    video.indir(callback, output)
    is_finished = True
    file_size_thread.join()
    callback({"status": "finished"})
    del tmp


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
