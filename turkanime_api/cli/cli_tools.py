from os import name,system
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
        if hook["status"] in ("finished","downloading") and "downloaded_bytes" in hook:
            descp = "İndiriliyor.."
            if hook["downloaded_bytes"] >= hook["total_bytes"]:
                descp = "İndirildi!"
            if not self.progress.tasks:
                task_id = self.progress.add_task(descp, total=hook["total_bytes"])
            else:
                task_id = self.progress.tasks[0].id
            self.progress.update(task_id,description=descp,completed=hook["downloaded_bytes"])
        if hook["status"] == "error":
            if self.progress.tasks:
                # TODO: hata mesajı gösterilecek
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
            pass # TODO: hata mesajı falan gösterilmeli
        if self.progress.tasks:
            task_id = self.progress.tasks[0].id
        else:
            task_id = self.progress.add_task(msg, total=hook["total"])
        completed = hook["total"] if hook["status"] == "çalışıyor" else hook["current"]
        self.progress.update(task_id, completed=completed, description=msg)


def indirme_task_cli(bolum_,table_,dosya_=None):
    """ Progress barı dinamik olarak güncellerken indirme yapar. """
    vid_cli = VidSearchCLI()
    dl_cli = DownloadCLI()
    table_.add_row(Panel.fit(
            Group(vid_cli.progress, dl_cli.progress),
            title=bolum_.slug,
            border_style="green"))
    table_.add_row("")
    # En iyi ve çalışan videoları filtrele.
    best_video = bolum_.best_video(
        by_res=dosya_.ayarlar["max resolution"],
        callback=vid_cli.callback)
    # En iyi videoyu indir ve işaretle.
    if best_video:
        best_video.indir(
            callback = dl_cli.ytdl_callback,
            output = dosya_.ayarlar["indirilenler"])
        if dosya_:
            dosya_.set_gecmis(bolum_.anime.slug, bolum_.slug, "indirildi")


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
