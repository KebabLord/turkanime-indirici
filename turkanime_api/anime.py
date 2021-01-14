from os import system,path,mkdir
from time import sleep
from configparser import ConfigParser

from .players import urlGetir

class animeSorgula():
    def __init__(self,driver=None):
        self.driver=driver
        self.seri=None

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
        self.seri=anime_ismi
        self.driver.get("https://www.turkanime.net/anime/{}".format(anime_ismi))
        sleep(3)

        liste = []
        for i in self.driver.find_elements_by_css_selector(".bolumAdi"):
            parent = i.find_element_by_xpath("..")
            url = parent.get_attribute("href").split("video/")[1]
            title = parent.get_attribute("innerText")
            liste.append( (title,url) )
            #        Bölüm Title, Bölüm Url
        return liste

    def listele(self,answers):
        """ PyInquirer İçin Seçenek Listele """
        if 'anime_ismi' in answers:
            results = self.getBolumler(answers["anime_ismi"])
        else:
            results = self.animeAra(answers["anahtar_kelime"])

        bolumler=[{"name":name,"value":url} for name,url in results]
        return bolumler


def animeIndir(bolumler,driver,seri):
    parser = ConfigParser()
    parser.read("./config.ini")
    dlFolder = parser.get("TurkAnime","indirilenler")

    if not path.isdir(f"{dlFolder}/{seri}"):
        mkdir(f"{dlFolder}/{seri}")

    for bolum in bolumler:
        driver.get(f"https://turkanime.net/video/{bolum}")
        sleep(5)
        print(f"\n{driver.title} indiriliyor.")
        url = urlGetir(driver)
        suffix="--referer https://video.sibnet.ru/" if "sibnet" in url else ""
        system(f"youtube-dl --no-warnings -o '{dlFolder}/{seri}/{bolum}.%(ext)s' '{url}' {suffix}")
    return True

def animeOynat(bolum,driver):
    driver.get(f"https://turkanime.net/video/{bolum}")
    url = urlGetir(driver)

    parser = ConfigParser()
    parser.read("./config.ini")

    suffix ="--referrer https://video.sibnet.ru/ " if  "sibnet" in url else ""
    suffix+=f"--record-file=./Kayıtlar/{bolum} " if parser.getboolean("TurkAnime","izlerken kaydet") else ""

    system(f"mpv '{url}' {suffix} ")
    return True
