""" TürkAnimu Downloader v7 """
from os import path,mkdir,name,environ
from sys import exit as kapat
from time import sleep
from atexit import register
from selenium.common.exceptions import WebDriverException
from rich.progress import Progress, BarColumn, SpinnerColumn
from rich import print as rprint
from questionary import select,autocomplete,checkbox

from turkanime_api import AnimeSorgula,Anime,DosyaManager,gereksinim_kontrol
from turkanime_api import elementi_bekle,webdriver_hazirla,prompt_tema,clear

dosya = DosyaManager()
sep = ";" if name=="nt" else ":"
environ["PATH"] +=  sep + dosya.ROOT + sep

with Progress(SpinnerColumn(), '[progress.description]{task.description}', BarColumn(bar_width=40)) as progress:
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

clear()
rprint("[green]!)[/green] Üst menülere dönmek için Ctrl+C kullanabilirsiniz.\n")
sleep(2.5)

while True:
    clear()
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
        clear()
        try:
            secilen_seri = autocomplete(
                'Animeyi yazın',
                choices=sorgu.get_seriler(),
                style=prompt_tema
            ).ask()
            seri_slug = sorgu.tamliste[secilen_seri]
        except KeyError:
            rprint("[red][strong]Aradığınız anime bulunamadı.[/strong][red]")
            continue

        bolumler = sorgu.get_bolumler(secilen_seri)
        set_prev = lambda x: [i for i in bolumler if i["value"]==x].pop()
        previous = None
        while True:
            if "izle" in islem:
                sorgu.mark_bolumler(seri_slug,bolumler,islem="izlendi")
                previous = sorgu.son_bolum if previous is None else previous
                clear()
                secilen = select(
                    message='Bölüm seç',
                    choices=bolumler,
                    style=prompt_tema,
                    default=previous
                ).ask(kbi_msg="")
                if secilen:
                    previous = set_prev(secilen)
            else:
                sorgu.mark_bolumler(seri_slug,bolumler,islem="indirildi")
                previous = sorgu.son_bolum if previous is None else previous
                clear()
                secilen = checkbox(
                    message = "Bölüm seç",
                    choices=bolumler,
                    style=prompt_tema,
                    initial_choice=previous
                ).ask(kbi_msg="")
                if secilen:
                    previous = set_prev(secilen[-1])

            # Bölüm seçim ekranı iptal edildiyse
            if not secilen:
                break
            anime = Anime(driver, sorgu.anime_ismi ,secilen)

            if islem=="Anime izle":
                anime.oynat()
            else:
                anime.indir()

    elif "Ayarlar" in islem:
        dosya = DosyaManager()
        ayar = dosya.ayar
        tr = lambda x: "AÇIK" if x else "KAPALI"
        while True:
            _otosub  = ayar.getboolean("TurkAnime","manuel fansub")
            _watched = ayar.getboolean("TurkAnime","izlendi ikonu")
            _otosave = ayar.getboolean("TurkAnime","izlerken kaydet")
            ayarlar = [
                'İndirilenler klasörünü seç',
                f'İzlerken kaydet: {tr(_otosave)}',
                f'Manuel fansub seç: {tr(_otosub)}',
                f'İzlendi/İndirildi ikonu: {tr(_watched)}',
                'Geri dön'
            ]
            clear()
            cevap = select(
                'İşlemi seç',
                ayarlar,
                style=prompt_tema,
                instruction=" "
                ).ask()
            if cevap == ayarlar[0]:
                from easygui import diropenbox
                indirilenler_dizin=diropenbox()
                if indirilenler_dizin:
                    ayar.set('TurkAnime','indirilenler',indirilenler_dizin)

            elif cevap == ayarlar[1]:
                ayar.set('TurkAnime','izlerken kaydet',str(not _otosave))
                if not path.isdir(path.join(".","Kayıtlar")):
                    mkdir(path.join(".","Kayıtlar"))

            elif cevap == ayarlar[2]:
                ayar.set('TurkAnime','manuel fansub',str(not _otosub))

            elif cevap == ayarlar[3]:
                ayar.set('TurkAnime','izlendi ikonu',str(not _watched))

            else:
                break
            dosya.save_ayarlar()
            sorgu.son_bolum=None

    elif "Kapat" in islem:
        break


""" Poetry script'leri modül gibi çalışmaya zorladığından
    limitasyonu aşmak için kirli bir çözüm.
"""
run = lambda: None
if __name__=="__main__":
    run()
