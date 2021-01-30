""" TürkAnimu Downloader v5.2 """
from os import path,mkdir
from atexit import register
from configparser import ConfigParser
import questionary

from turkanime_api import AnimeSorgula,Anime,gereksinim_kontrol,elementi_bekle,webdriver_hazirla

print('TürkAnimu İndirici - github/Kebablord')
gereksinim_kontrol()
driver = webdriver_hazirla()
register(lambda: (print("Program kapatılıyor..",end="\r") or driver.quit()))
driver.get("https://turkanime.net/kullanici/anonim")
elementi_bekle(".navbar-nav",driver)
sorgu = AnimeSorgula(driver)

while True:
    islem = questionary.select(
        "İşlemi seç",
        choices=['Anime izle',
                'Anime indir',
                'Ayarlar',
                'Kapat']
    ).ask()

    if "Anime" in islem:
        try:
            secilen_seri = questionary.autocomplete(
                'Animeyi seçin',
                choices=sorgu.get_seriler()
            ).ask()

            # Anime'yi ara ve bölüm seç
            secilen_bolumler = questionary.prompt({
                'type': "checkbox" if "indir" in islem else "select",
                'message': 'Bölüm seç',
                'name': 'anime_bolum',
                'choices': sorgu.get_bolumler(secilen_seri)
            })['anime_bolum']

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
            opsiyon = questionary.select(
                'İşlemi seç',
                ['İndirilenler klasörünü seç',
                f'İzlerken kaydet: {isAutosave}',
                'Geri dön'
                ]).ask()
            if opsiyon == 'İndirilenler klasörünü seç':
                from easygui import diropenbox
                parser.set('TurkAnime','indirilenler',diropenbox())
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
