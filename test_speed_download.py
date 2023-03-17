from os import path,mkdir,name,environ, system
from sys import exit as kapat
from time import sleep
from atexit import register
from selenium.common.exceptions import WebDriverException
from rich import print as rprint
from questionary import select,autocomplete,checkbox, confirm, text

import shutil

from turkanime_api import (
    AnimeSorgula,
    Anime,
    DosyaManager,
    gereksinim_kontrol,
    elementi_bekle,
    webdriver_hazirla,
    prompt_tema,
    clear,
    create_progress
)

from time import perf_counter

if __name__ == '__main__':

    dosya = DosyaManager()
    SEP = ";" if name=="nt" else ":"
    environ["PATH"] +=  SEP + dosya.ROOT + SEP

    with create_progress() as progress:
        task = progress.add_task("[cyan]Sürücü başlatılıyor..", start=False)
        gereksinim_kontrol(progress)
        driver = webdriver_hazirla(progress)
        register(lambda: (print("Program kapatılıyor..",end="\r") or driver.quit()))

        progress.update(task, description="[cyan]TürkAnime'ye bağlanılıyor..")
        try:
            driver.get("https://turkanime.co/kullanici/anonim")
            elementi_bekle(".navbar-nav",driver)
        except (ConnectionError,WebDriverException):
            progress.update(task,visible=False)
            rprint("[red][strong]TürkAnime'ye ulaşılamıyor.[/strong][red]")
            kapat(1)
        sorgu = AnimeSorgula(driver)
        progress.update(task,visible=False)


    anime = Anime(driver, 'one-piece', ['one-piece-1-bolum', 'one-piece-2-bolum'])

    single_thread_speed = 0
    multi_thread_speed = 0
    
    shutil.rmtree('one-piece')

    start = perf_counter()
    anime.indir()
    single_thread_speed = perf_counter() - start

    shutil.rmtree('one-piece')

    start = perf_counter()
    anime.multi_indir(2)
    multi_thread_speed = perf_counter() - start

    print(f'single {single_thread_speed}')
    print(f'multi {multi_thread_speed}')