from os import name,path,mkdir
from atexit import register
from threading import Thread
from configparser import ConfigParser
from PyInquirer import prompt
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

from lib.anime import animeSorgula,animeIndir,animeOynat

def cleanPrint(string): ## Statik yazı printleme fonksiyonu
    print('\033[2K\033[1G',end="\r")
    print(string,end='\r')

# Selenium'u başlat
if __name__ == '__main__':
    print('TürkAnimu İndirici - github/Kebablord')

    def at_exit(): ## Program kapatıldığında
        cleanPrint("Program kapatılıyor..")
        driver.quit()
    register(at_exit)

    options = Options()
    options.add_argument('--headless')
    cleanPrint("Sürücü başlatılıyor...")
    profile = webdriver.FirefoxProfile()
    profile.set_preference('permissions.default.image', 2)
    profile.set_preference("network.proxy.type", 0)
    if name == 'nt': # WINDOWS
        driver = webdriver.Firefox(profile, options=options, executable_path=r'geckodriver.exe')
    else:            # LINUX
        driver = webdriver.Firefox(profile, options=options)

    isExit = False
    def popupKiller(driver):
        while not isExit:
            if len(driver.window_handles)>1:
                driver.switch_to.window(driver.window_handles[1])
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                print("killed smth")
    killerPopup = Thread(target=popupKiller,name="Pop-up killer",args=(driver,))
    killerPopup.start()

    sorgu = animeSorgula(driver)
    while True:
        # Kullanıcıya ne yapmak istediğini sor
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
            tip = "checkbox" if "indir" in islem else "list"

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
                'type': tip,
                'message': 'Bölüm seç',
                'name': 'anime_bolum',
                'choices': sorgu.listele
            }])["anime_bolum"]

            if islem=="Anime izle":
                animeOynat(secilen_bolumler,driver=driver)
            else:
                animeIndir(secilen_bolumler,driver=driver)

        elif "Ayarlar" in islem:
            parser = ConfigParser()
            while True:
                parser.read("./config.ini")
                isAutosave   = parser.getboolean("TurkAnime","izlerken kaydet")
                isAutofansub = parser.getboolean("TurkAnime","oto fansub")
                dlFolder     = parser.get("TurkAnime","indirilenler")
                opsiyon = prompt([{
                    'type': 'list',
                    'name': 'ayar',
                    'message': 'İşlemi seç',
                    'choices': ['İndirilenler klasörünü seç',
                                f'İzlerken kaydet: {isAutosave}',
                                f'Fansub ve playerı otomatik seç: {isAutofansub}',
                                'Geri dön']
                    }])['ayar']
                if opsiyon == 'İndirilenler klasörünü seç':
                    from easygui import diropenbox
                    parser.set('TurkAnime','indirilenler',diropenbox())

                elif opsiyon == f'İzlerken kaydet: {isAutosave}':
                    parser.set('TurkAnime','izlerken kaydet',str(not isAutosave ))
                    if path.isdir('./Kayıtlar'):
                        mkdir("./Kayıtlar")

                elif opsiyon == f'Fansub ve playerı otomatik seç: {isAutofansub}':
                    parser.set('TurkAnime','oto fansub',str(not isAutofansub))
                else:
                    break

                with open("./config.ini","w") as f:
                    parser.write(f)

        elif "Kapat" in islem:
            isExit = True
            break
