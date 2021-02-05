""" TürkAnimu Downloader v5.3 """
from os import path,mkdir
from sys import exit as kapat
from atexit import register
from configparser import ConfigParser
from selenium.common.exceptions import WebDriverException
from rich.progress import Progress, BarColumn, SpinnerColumn
from rich import print as rprint
from questionary import select,autocomplete,prompt

from turkanime_api import AnimeSorgula,Anime,gereksinim_kontrol
from turkanime_api import elementi_bekle,webdriver_hazirla,prompt_tema

with Progress(SpinnerColumn(), '[progress.description]{task.description}', BarColumn(bar_width=40)) as progress:
    task = progress.add_task("[cyan]Sürücü başlatılıyor..", start=False)
    gereksinim_kontrol()
    driver = webdriver_hazirla()
    register(lambda: (print("Program kapatılıyor..",end="\r") or driver.quit()))

    progress.update(task, description="[cyan]TürkAnime'ye bağlanılıyor..")
    try:
        driver.get("https://turkanime.net/kullanici/anonim")
        elementi_bekle(".navbar-nav",driver)
    except (ConnectionError,WebDriverException):
        progress.update(task,visible=False)
        rprint("[red][strong]TürkAnime'ye ulaşılamıyor.[/strong][red]")
        kapat(1)
    sorgu = AnimeSorgula(driver)
    progress.update(task,visible=False)


while True:
    islem = select(
        "İşlemi seç",
        choices=['Anime izle',
                'Anime indir',
                'Ayarlar',
                'Kapat'],
        style=prompt_tema,
        instruction=" "
    ).ask()

    if "Anime" in islem:
        try:
            secilen_seri = autocomplete(
                'Animeyi yazın',
                choices=sorgu.get_seriler(),
                style=prompt_tema
            ).ask()

            secilen_bolumler = prompt({
                'type': "checkbox" if "indir" in islem else "select",
                'message': 'Bölüm seç',
                'name': 'anime_bolum',
                'choices': sorgu.get_bolumler(secilen_seri)},
                style=prompt_tema,
                kbi_msg=""
            )['anime_bolum']

        except KeyError:
            continue

        anime = Anime(driver, sorgu.anime_ismi ,secilen_bolumler)

        if islem=="Anime izle":
            anime.oynat()
        else:
            anime.indir()

    elif "Ayarlar" in islem:
        parser = ConfigParser()
        while True:
            parser.read(path.join(".","config.ini"))
            isAutosave   = parser.getboolean("TurkAnime","izlerken kaydet")
            dlFolder     = parser.get("TurkAnime","indirilenler")
            opsiyon = select(
                'İşlemi seç',
                ['İndirilenler klasörünü seç',
                f'İzlerken kaydet: {isAutosave}',
                'Geri dön'],
                style=prompt_tema,
                instruction=" ",
                ).ask()
            if opsiyon == 'İndirilenler klasörünü seç':
                from easygui import diropenbox
                indirilenler_dizin=diropenbox()
                if indirilenler_dizin:
                    parser.set('TurkAnime','indirilenler',indirilenler_dizin)
            elif opsiyon == f'İzlerken kaydet: {isAutosave}':
                parser.set('TurkAnime','izlerken kaydet',str(not isAutosave))
                if not path.isdir(path.join(".","Kayıtlar")):
                    mkdir(path.join(".","Kayıtlar"))
            else:
                break

            with open("./config.ini","w") as f:
                parser.write(f)

    elif "Kapat" in islem:
        break
