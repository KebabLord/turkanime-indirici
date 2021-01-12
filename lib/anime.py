from os import system
from time import sleep
from configparser import ConfigParser
from PyInquirer import prompt

from lib.players import players

class animeSorgula():
    def __init__(self,driver=None):
        self.driver=driver

    def animeAra(self, aranan_anime):
        """ Animeyi arayıp geriye (title,url) formatında sonuçları döndürür. """
        self.driver.get(f"https://www.turkanime.net/arama?arama={aranan_anime}")
        if "/anime/" in self.driver.current_url:
            liste = [[self.driver.title, self.driver.current_url.split("anime/")[1]]]
            self.driver.get("about:blank")
            return liste

        liste = []
        for i in self.driver.find_elements_by_css_selector(".panel-title a"):
            liste.append( (i.text, i.get_attribute("href").split("anime/")[1]) )
            #         Anime Title, Anime Url
        return liste

    def getBolumler(self, anime_ismi):
        """ Animenin bölümlerini (bölüm,title) formatında döndürür. """
        self.driver.get("https://www.turkanime.net/anime/{}".format(anime_ismi))
        sleep(3)

        liste = []
        for i in self.driver.find_elements_by_css_selector(".bolumAdi"):
            parent = i.find_element_by_xpath("..")
            url = parent.get_attribute("href").split("video/")[1]
            title = parent.get_attribute("innerText")
            liste.append( (title,url) )
            #            Bölüm Title, Bölüm Url
        return liste

    def listele(self,answers):
        """ PyInquirer İçin Seçenek Listele """
        if 'anime_ismi' in answers:
            results = self.getBolumler(answers["anime_ismi"])
        else:
            results = self.animeAra(answers["anahtar_kelime"])

        bolumler=[{"name":name,"value":url} for name,url in results]
        return bolumler


def animeIndir(bolumler,driver):
    """ Çalışan bir video bulana dek fansub ve alternatifleri itere et """
    parser = ConfigParser()
    parser.read("./config.ini")
    dlFolder = parser.get("TurkAnime","indirilenler")

    for bolum in bolumler:
        driver.get(f"https://turkanime.net/video/{bolum}")
        sleep(5)
        print(f"{driver.title} indiriliyor...")
        li_fansub = [i.text for i in driver.find_elements_by_css_selector("div.panel-body div.pull-right button")]

        for fansub in li_fansub:
            driver.find_element_by_xpath(f"//*[contains(text(), '{fansub}')]").click()
            sleep(5)
            li_alternatif = [i.text for i in driver.find_elements_by_xpath("//div[@class='panel-body']/div[@class='btn-group']/button")]

            for player in players:
                if player in li_alternatif:
                    sleep(3)
                    driver.find_element_by_xpath(f"//*[contains(text(), '{player}')]").click()
                    sleep(5)
                    url = players[ player ](driver)
                    driver.switch_to.default_content()

                    if url and system(f"youtube-dl --no-warnings -F '{url}'")==0:
                        playername = player
                        print(f"{playername.title()} alternatifi doğrulandı.")
                        break
                    print(f"{player} alternatifindeki videoya ulaşılamıyor.")
            else:
                continue
            break

        suffix="--referer https://video.sibnet.ru/" if playername == "SIBNET" else ""
        system(f"youtube-dl --no-warnings -o "{dlFolder}/{bolum}.%(ext)s" '{url}' {suffix}")


def animeOynat(bolum,driver):
    """ Manuel olarak fansub ve alternatif seçtirir """
    driver.get(f"https://turkanime.net/video/{bolum}")
    stage = "fansubSec"
    while True:
        # Fansubu belirle
        if stage == "fansubSec":
            driver.switch_to.default_content()
            fansublar = {}
            for fansub in driver.find_elements_by_css_selector("div.panel-body div.pull-right button"):
                fansublar[fansub.text] = fansub

            secilen_fansub = prompt([{
                'type': 'list',
                'name': 'fansub',
                'message': 'Fansub seç',
                'choices': list(fansublar)+["Geri dön"]
            }])['fansub']

            if secilen_fansub=="Geri dön":
                return False

            stage="platformSec"
            fansublar[secilen_fansub].click()
            sleep(4)

        # Alternatifi belirle
        elif stage == "platformSec":
            driver.switch_to.default_content()

            alternatifler = []
            for alternatif in driver.find_elements_by_xpath("//div[@class='panel-body']/div[@class='btn-group']/button"):
                alternatifler.append({
                    'name':alternatif.text,
                    'value':alternatif,
                    "disabled": False if alternatif.text in list(players) else "!"
                })

            obj = prompt([{
                'type': 'list',
                'name': 'alternatif',
                'message': 'Video platformu seç',
                'choices': alternatifler+["Geri dön"]
            }])['alternatif']

            if obj=="Geri dön":
                stage="fansubSec"
                continue

            playername=obj.text
            obj.click()
            sleep(3)

            url = players[ playername ](driver)

            if url and system(f"youtube-dl -q --no-warnings -F '{url}'") == 0:
                print('Videonun aktif olduğu doğrulandı.')
            else:
                print(f"{playername.title()} alternatifindeki videoya ulaşılamıyor.")
                continue

            # Oynat
            parser = ConfigParser()
            parser.read("./config.ini")

            suffix ="--referrer https://video.sibnet.ru/ " if playername == "SIBNET" else ""
            suffix+=f"--record-file=./Kayıtlar/{bolum} " if parser.getboolean("TurkAnime","izlerken kaydet") else ""

            system(f"mpv '{url}' {suffix} ")
            return True
