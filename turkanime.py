""" TürkAnimu Downloader v7.0.7 """
from os import path,mkdir,name,environ
from sys import exit as kapat
from time import sleep
from atexit import register
from selenium.common.exceptions import WebDriverException
from rich import print as rprint
from questionary import select,autocomplete,checkbox, confirm, text
import requests

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

dosya = DosyaManager()
SEP = ";" if name=="nt" else ":"
environ["PATH"] +=  SEP + dosya.ROOT + SEP

def check_latest_version():
    """Github'daki en güncel versiyonu string olarak döndürür"""
    response = requests.get("https://api.github.com/repos/KebabLord/turkanime-indirici/releases/latest", timeout=3)
    return response.json()["tag_name"][1:]

def check_current_version():
    """Bilgisayardaki mevcut versiyonu string olarak döndürür"""
    with open("pyproject.toml", "r", encoding="UTF-8") as pp:
        pp_data = pp.read().split("\n")[2]
        return pp_data[pp_data.index("\"")+1:len(pp_data)-1]

son_versiyon = check_latest_version()
uygulama_versiyonu = check_current_version()

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

clear()
if uygulama_versiyonu != son_versiyon:
    rprint("[red]Uygulamanın sürümü güncel değil[red] [yellow]"+uygulama_versiyonu+"[yellow] -> [green]"+son_versiyon+"[green]")
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
                dosya = DosyaManager()
                max_dl = dosya.ayar.getint("TurkAnime","aynı anda indirme sayısı")
                if max_dl <= 1:
                    anime.indir()
                else:
                    rprint(f" [green]-[/green] Paralel indirme aktif. (max={max_dl})\n")
                    anime.multi_indir(max_dl)


    elif "Ayarlar" in islem:
        dosya = DosyaManager()
        ayar = dosya.ayar
        tr = lambda x: "AÇIK" if x else "KAPALI"
        while True:
            _otosub  = ayar.getboolean("TurkAnime","manuel fansub")
            _watched = ayar.getboolean("TurkAnime","izlendi ikonu")
            _otosave = ayar.getboolean("TurkAnime","izlerken kaydet")
            _max_dl  = ayar.get("TurkAnime","aynı anda indirme sayısı")
            ayarlar = [
                'İndirilenler klasörünü seç',
                f'İzlerken kaydet: {tr(_otosave)}',
                f'Manuel fansub seç: {tr(_otosub)}',
                f'İzlendi/İndirildi ikonu: {tr(_watched)}',
                f'Aynı anda indirme sayısı: {_max_dl}',
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

            elif cevap == ayarlar[4]:
                _max_dl = text(
                    message = f'Maksimum eş zamanlı kaç bölüm indirilsin?',
                    default = str(_max_dl),
                    style = prompt_tema
                ).ask(kbi_msg="")
                ayar.set('TurkAnime','aynı anda indirme sayısı',_max_dl)

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
