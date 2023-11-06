""" TürkAnimu Downloader """
from os import environ,name
from time import sleep
import sys
import atexit
from rich import print as rprint
from questionary import select,autocomplete,checkbox,confirm
from selenium.common.exceptions import WebDriverException


from ..webdriver import create_webdriver,elementi_bekle
from ..objects import Anime, Bolum
from .dosyalar import Dosyalar
from .gereksinimler import Gereksinimler, MISSING
from .cli_tools import prompt_tema,clear

# Uygulama dizinini sistem PATH'ına ekle.
SEP = ";" if name=="nt" else ":"
environ["PATH"] +=  SEP + Dosyalar().ta_path + SEP

def gereksinim_kontrol_cli():
    """ Gereksinimleri kontrol eder ve gerekirse indirip kurar."""
    gerek = Gereksinimler()
    if gerek.eksikler:
        eksik_msg = ""
        guide_msg = "\nManuel indirmek için:\nhttps://github.com/KebabLord/turkanime-indirici/wiki"
        for eksik,exit_code in gerek.eksikler:
            if exit_code is MISSING:
                eksik_msg += f"{eksik} yazılımı bulunamadı."
            else:
                eksik_msg += f"{eksik} yazılımı bulundu ancak çalıştırılamadı."
        print(eksik_msg,end="\n\n")
        if name=="nt" and confirm("Otomatik kurulsun mu?").ask():
            fails = gerek.otomatik_indir()
            eksik_msg = None, ""
            for fail in fails:
                if "err_msg" in fail:
                    eksik_msg += f"!) {fail['name']} indirilemedi\n"
                    if fail["err_msg"] != "":
                        eksik_msg += f"   -   {fail['err_msg'][:45]}...\n"
                elif "ext_code" in fail:
                    if fail["ext_code"] is MISSING:
                        eksik_msg += f"!) {fail['name']} kurulamadı.\n"
                    else:
                        eksik_msg += f"!) {fail['name']} çalıştırılamadı.\n"
            if fails:
                print(eksik_msg + guide_msg)
                input("\n(ENTER'a BASIN)")
                sys.exit(1)
        else:
            print(guide_msg)
            input("\n(ENTER'a BASIN)")
            sys.exit(1)


def to_choices(li):
    """ (name,value) formatını questionary choices formatına dönüştür. """
    assert len(li) != 0
    if isinstance(li[0], Bolum):
        return [{
            "name": str(b.title),
            "value": b
        } for b in li]
    return [{
        "name": str(n),
        "value": s
    } for s,n in li]


def menu_loop(driver):
    """ Ana menü interaktif navigasyonu """
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
        # Anime izle veya indir seçildiyse.
        if "Anime" in islem:
            # Seriyi seç.
            try:
                animeler = Anime.get_anime_listesi(driver)
                seri_ismi = autocomplete(
                    'Animeyi yazın',
                    choices = [n for s,n in animeler],
                    style = prompt_tema
                ).ask()
                seri_slug = [s for s,n in animeler if n==seri_ismi][0]
                anime = Anime(driver,seri_slug)
            except (KeyError,IndexError):
                rprint("[red][strong]Aradığınız anime bulunamadı.[/strong][red]")
                sleep(3)
                continue

            while True:
                if "izle" in islem:
                    bolum = select(
                        message='Bölüm seç',
                        choices= to_choices(anime.bolumler),
                        style=prompt_tema,
                        #default=previous
                    ).ask(kbi_msg="")
                    ...
                else:
                    bolumler = checkbox(
                        message = "Bölüm seç",
                        choices=to_choices(anime.bolumler),
                        style=prompt_tema,
                        #initial_choice=previous
                    ).ask(kbi_msg="")
                    ...
        ...


def main():
    # Selenium'u başlat.
    driver = create_webdriver()
    try:
        driver.get("https://turkanime.co/kullanici/anonim")
        elementi_bekle(".navbar-nav",driver)
    except (ConnectionError,WebDriverException):
        rprint("[red][strong]TürkAnime'ye ulaşılamıyor.[/strong][red]")
        sys.exit(1)

    clear()
    rprint("[green]!)[/green] Üst menülere dönmek için Ctrl+C kullanabilirsiniz.\n")
    sleep(2.5)

    menu_loop(driver)



if __name__ == '__main__':
    main()