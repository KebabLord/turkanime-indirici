from os import name,path,mkdir
from atexit import register
from configparser import ConfigParser
from time import sleep
import questionary
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from turkanime_api import AnimeSorgula,Anime,gereksinim_kontrol

print('TürkAnimu İndirici - github/Kebablord')
gereksinim_kontrol()

def at_exit(): # Program kapatıldığında
    print(" "*50+"\rProgram kapatılıyor..",end="\r")
    driver.quit()
register(at_exit)

print(" "*50+"\rSürücü başlatılıyor...",end="\r")

options = Options()
options.add_argument('--headless')
profile = webdriver.FirefoxProfile()
profile.set_preference("dom.webdriver.enabled", False)
profile.set_preference('useAutomationExtension', False)
profile.set_preference('permissions.default.image', 2)
profile.set_preference("network.proxy.type", 0)
profile.update_preferences()
desired = webdriver.DesiredCapabilities.FIREFOX
if name == 'nt':
    driver = webdriver.Firefox(profile, options=options,service_log_path='NUL', executable_path=r'geckodriver.exe', desired_capabilities=desired)
else:
    driver = webdriver.Firefox(profile, options=options, service_log_path='/dev/null',desired_capabilities=desired)

driver.get("https://turkanime.net/kullanici/anonim")
sleep(7)

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
