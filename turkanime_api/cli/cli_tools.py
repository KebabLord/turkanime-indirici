from sys import exit as kapat
import subprocess as sp
from os import name,system
from time import sleep
from prompt_toolkit import styles
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import SessionNotCreatedException
from rich.progress import Progress, BarColumn, SpinnerColumn
from questionary import confirm


def clear():
    """ Daha kompakt görüntü için her prompt sonrası clear
        Debug yapacaksanız devre dışı bırakmanız önerilir.
    """
    system('cls' if name == 'nt' else 'clear')

class CliProgress():
    """ Progress barı yaratma ve takip etme objesi. """
    def __init__(self,msg=None,hide_after=True):
        self._progress = None
        self.task_id = None
        self.hide_after = hide_after
        self.msg = msg

    @property
    def progress(self):
        """ Progress animasyonu objesi. """
        if self._progress is None:
            self._progress = Progress(
                SpinnerColumn(),
                '[progress.description]{task.description}',
                BarColumn(bar_width=40),
                transient=self.hide_after)
            self._progress.start()
        return self._progress

    def callback(self,current,total,msg=""):
        """ Paralel olmayan task'lar için tekil progress yönetimi. """
        if not self.progress.tasks:
            task_id = self.progress.add_task(f"[cyan]{msg}", total=total)
        self.progress.update(self.progress.tasks[0].id, completed=current)
        if self.progress.finished:
            self.progress.stop()
            self._progress = None

    def multi_callback(self,current,total,pname):
        """ Paralel senaryo için multi-task callback handling 
            task'ları ayırt edebilmek için pname parametresi zorunludur.
        """
        msg = "[cyan]"+pname
        for task in self.progress.tasks:
            if task.description == msg:
                task_id = task.id
                break
        else:
            task_id = self.progress.add_task(msg, total=total)

        self.progress.update(task_id, completed=current)
        if self.progress.finished:
            self.progress.stop()
            self.progress_ = None

    def __enter__(self):
        if not self.msg is None:
            self.progress.add_task(f"[cyan]{self.msg}", total=None)
        return self

    def __del__(self):
        if self._progress:
            self.progress.stop()

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

