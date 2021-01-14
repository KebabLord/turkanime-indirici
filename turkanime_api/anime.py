from os import system,path,mkdir
from time import sleep
from configparser import ConfigParser

from .players import url_getir

class AnimeSorgula():
    def __init__(self,driver=None):
        self.driver=driver
        self.seri=None

    def anime_ara(self, aranan_anime):
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

    def get_bolumler(self, anime_ismi):
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
            results = self.get_bolumler(answers["anime_ismi"])
        else:
            results = self.anime_ara(answers["anahtar_kelime"])

        bolumler=[{"name":name,"value":url} for name,url in results]
        return bolumler


class Anime():
    """ İstenilen bölümü izle, yada bölümleri indir. """

    def __init__(self,driver,seri,bolumler):
        self.driver = driver
        self.seri = seri
        self.bolumler = bolumler

    def indir(self):
        parser = ConfigParser()
        parser.read("./config.ini")
        dlfolder = parser.get("TurkAnime","indirilenler")

        if not path.isdir(f"{dlfolder}/{self.seri}"):
            mkdir(f"{dlfolder}/{self.seri}")

        for bolum in self.bolumler:
            self.driver.get(f"https://turkanime.net/video/{bolum}")
            sleep(5)
            print(f"\n{self.driver.title} indiriliyor.")
            url = url_getir(self.driver)
            suffix="--referer https://video.sibnet.ru/" if "sibnet" in url else ""
            system(f"youtube-dl --no-warnings -o '{dlfolder}/{self.seri}/{bolum}.%(ext)s' '{url}' {suffix}")
        return True

    def oynat(self):
        self.driver.get(f"https://turkanime.net/video/{self.bolumler}")
        url = url_getir(self.driver)

        parser = ConfigParser()
        parser.read("./config.ini")

        suffix ="--referrer https://video.sibnet.ru/ " if  "sibnet" in url else ""
        suffix+=f"--record-file=./Kayıtlar/{self.bolumler} " if parser.getboolean("TurkAnime","izlerken kaydet") else ""

        system(f"mpv '{url}' {suffix} ")
        return True
