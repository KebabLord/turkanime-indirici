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

def create_progress(transient=False):
    """ Progress animasyonu objesini döndürüyor. """
    return Progress(
        SpinnerColumn(),
        '[progress.description]{task.description}',
        BarColumn(bar_width=40),
        transient=transient
    )


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
    ('disabled', 'fg:#858585 italic')
])

