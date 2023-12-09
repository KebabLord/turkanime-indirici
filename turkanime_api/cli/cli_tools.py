from os import name,system
from prompt_toolkit import styles

from rich.progress import (
    Progress,
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

class CliProgress():
    """ Progress barı yaratma ve takip etme objesi. """
    def __init__(self,msg=None,is_indirme=False,hide_after=True):
        self.is_indirme = is_indirme
        self.hide_after = hide_after
        self._progress = None
        self.task_id = None
        self.msg = msg
        self.tasks = {}

    @property
    def progress(self):
        """ Progress animasyonu objesi. """
        if self._progress is None:
            cols = (
                SpinnerColumn("bouncingBar"),
                '[progress.description]{task.description}',
                BarColumn(bar_width=40))
            if self.is_indirme:
                cols += (
                    TaskProgressColumn(),
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    TimeRemainingColumn()
                )
            self._progress = Progress(*cols, transient = self.hide_after)
            self._progress.start()
        return self._progress

    def callback(self,current,total,msg=""):
        """ Paralel olmayan task'lar için tekil progress yönetimi. """
        if not self.progress.tasks:
            self.progress.add_task(f"[cyan]{msg}", total=total)
        self.progress.update(self.progress.tasks[0].id, completed=current)
        if self.progress.finished:
            self.progress.stop()
            self._progress = None

    def bestvid_callback(self, hook):
        """ Objects.Video.best_video methodu için callback handler. """
        msg = "[cyan]"
        if hook.get("player"):
            msg = msg + f'{hook["player"]} {hook["status"]}.'
        elif hook.get("status") == "hiçbiri çalışmıyor":
            ...

        uid = hook.get("object")
        for task_uid,task_id in self.tasks.items():
            if task_uid == uid:
                break
        else:
            task_id = self.progress.add_task(msg, total=hook["total"])
            self.tasks[uid] = task_id
        self.progress.update(task_id, completed=hook["current"], description=msg)

    def ytdl_callback(self,hook):
        """ ydl_options['progress_hooks'] için callback handler. """
        info = hook["info_dict"]
        uid = info["_filename"]
        if hook["status"] in ("finished","downloading") and "downloaded_bytes" in hook:
            if uid in self.tasks:
                task_id = self.tasks[uid]
            else:
                descp = "["+info['webpage_url_domain'].split(".")[-2].upper()+"] "
                descp += info["_filename"].split(".")[0]
                task_id = self.progress.add_task(descp, total=hook["total_bytes"])
                self.tasks[uid] = task_id
            self.progress.update(task_id,completed=hook["downloaded_bytes"])
        if hook["status"] == "error":
            if uid in self.tasks:
                task_id = self.tasks[uid]
                self.progress.stop_task(task_id)

    def __enter__(self):
        if not self.msg is None:
            self.progress.add_task(f"[cyan]{self.msg}", total=None)
        return self

    def __del__(self):
        if self._progress:
            self.progress.stop()
        self.tasks = {}

    def __exit__(self, _=None, __=None, ___=None):
        self.__del__()


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
