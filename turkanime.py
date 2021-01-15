from os import name,path,mkdir
from atexit import register
from configparser import ConfigParser
from PyInquirer import prompt
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from turkanime_api import AnimeSorgula,Anime,clean_print

print('TürkAnimu İndirici - github/Kebablord')

def at_exit(): # Program kapatıldığında
    clean_print("Program kapatılıyor..")
    driver.quit()
register(at_exit)

options = Options()
options.add_argument('--headless')
clean_print("Sürücü başlatılıyor...")
profile = webdriver.FirefoxProfile()
profile.set_preference('permissions.default.image', 2)
profile.set_preference("network.proxy.type", 0)

if name == 'nt': # WINDOWS
    driver = webdriver.Firefox(profile, options=options, executable_path=r'geckodriver.exe')
else:            # LINUX
    driver = webdriver.Firefox(profile, options=options)

sorgu = AnimeSorgula(driver)
while True:
    islem = prompt([{
        'type': 'list',
        'name': 'islem',
        'message': 'İşlemi seç',
        'choices': [
            'Anime izle',
            'Anime indir',
            'Ayarlar',
            'Kapat']
        }])['islem']

    if "Anime" in islem:
        # Anime'yi ara ve bölüm seç
        secilen_bolumler = prompt([{
            'type': 'input',
            'name': 'anahtar_kelime',
            'message': 'Animeyi ara',
            },{
            'type': 'list',
            'name': 'anime_ismi',
            'message': 'Animeyi seç',
            'choices': sorgu.listele,
            },{
            'type': "checkbox" if "indir" in islem else "list",
            'message': 'Bölüm seç',
            'name': 'anime_bolum',
            'choices': sorgu.listele
        }])["anime_bolum"]

        anime = Anime(driver,sorgu.seri,secilen_bolumler)

        if islem=="Anime izle":
            anime.oynat()
        else:
            anime.indir()

    elif "Ayarlar" in islem:
        parser = ConfigParser()
        while True:
            parser.read("./config.ini")
            isAutosave   = parser.getboolean("TurkAnime","izlerken kaydet")
            dlFolder     = parser.get("TurkAnime","indirilenler")
            opsiyon = prompt([{
                'type': 'list',
                'name': 'ayar',
                'message': 'İşlemi seç',
                'choices': ['İndirilenler klasörünü seç',
                            f'İzlerken kaydet: {isAutosave}',
                            'Geri dön']
                }])['ayar']
            if opsiyon == 'İndirilenler klasörünü seç':
                from easygui import diropenbox
                parser.set('TurkAnime','indirilenler',diropenbox())
            elif opsiyon == f'İzlerken kaydet: {isAutosave}':
                parser.set('TurkAnime','izlerken kaydet',str(not isAutosave ))
                if path.isdir('./Kayıtlar'):
                    mkdir("./Kayıtlar")
            else:
                break

            with open("./config.ini","w") as f:
                parser.write(f)

    elif "Kapat" in islem:
        break
