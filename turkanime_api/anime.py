from os import system,path,mkdir
from configparser import ConfigParser
from bs4 import BeautifulSoup as bs4

from .players import url_getir,elementi_bekle

class AnimeSorgula():
    def __init__(self,driver=None):
        self.driver=driver
        self.seri=None

    def anime_ara(self, aranan_anime):
        """ Animeyi arayıp sonuçları {title,slug,code} formatında döndürür. """
        print(" "*50+"\rTürkanimeye bağlanılıyor..",end="\r")
        self.driver.get(f"https://www.turkanime.net/arama?arama={aranan_anime}")
        elementi_bekle(".panel-ust",self.driver)

        liste = []
        if "/anime/" in self.driver.current_url:
            liste.append({
                "title" : self.driver.title,
                "slug"  : self.driver.current_url.split("anime/")[1],
                "code"  : self.driver.find_element_by_css_selector(".imaj img").get_attribute("data-src").split("serilerb/")[1][:-4]
            })
            return liste

        elementi_bekle(".panel-ust-ic",self.driver)
        for card in self.driver.find_elements_by_css_selector(".panel.panel-visible"):
            liste.append({
                "title" : card.find_element_by_class_name("panel-ust-ic").text,
                "slug"  : card.find_element_by_tag_name("a").get_attribute("href").split("anime/")[1],
                "code"  : card.find_element_by_tag_name("img").get_attribute("data-src").split("seriler/")[1][:-4]
            })
        return liste

    def get_bolumler(self, anime_code):
        """ Animenin bölümlerini (bölüm,title) formatında döndürür. """
        print(" "*50+"\rBölümler yükleniyor..",end="\r")
        raw = self.driver.execute_script(f"return $.get('https://www.turkanime.net/ajax/bolumler&animeId={anime_code}')")
        soup = bs4(raw,"html.parser")
        soup.findAll("a",{"title":"İzlediklerime Ekle"})

        bolumler = []
        for bolum in soup.findAll("span",{"class":"bolumAdi"}):
            bolumler.append(
                (bolum.text, bolum.findParent().get("href").split("video/")[1])
            )
        return bolumler

    def listele(self,answers):
        """ PyInquirer İçin Seçenek Listele """
        # Bölümler
        if 'anime_ismi' in answers:
            results = self.get_bolumler(answers["anime_ismi"][1])
            self.seri=answers["anime_ismi"][0]
            return [{"name":title,"value":slug} for title,slug in results]

        # Anime arama sonuçları
        results = self.anime_ara(answers["anahtar_kelime"])
        return [{"name":i["title"],"value":(i["slug"],i["code"])} for i in results]


class Anime():
    """ İstenilen bölümü izle, yada bölümleri indir. """

    def __init__(self,driver,seri,bolumler):
        self.driver = driver
        self.seri = seri
        self.bolumler = bolumler

    def indir(self):
        parser = ConfigParser()
        parser.read(path.join(".","config.ini"))
        dlfolder = parser.get("TurkAnime","indirilenler")

        if not path.isdir(path.join(dlfolder,self.seri)):
            mkdir(path.join(dlfolder,self.seri))

        for bolum in self.bolumler:
            print(" "*50+"\rBölüm getiriliyor..",end="\r")
            self.driver.get(f"https://turkanime.net/video/{bolum}")
            print(" "*50+f"\r\n{self.driver.title} indiriliyor:")
            url = url_getir(self.driver)
            suffix="--referer https://video.sibnet.ru/" if "sibnet" in url else ""
            system(f'youtube-dl --no-warnings -o "{path.join(dlfolder,self.seri,bolum)}.%(ext)s" "{url}" {suffix}')
        return True

    def oynat(self):
        self.driver.get(f"https://turkanime.net/video/{self.bolumler}")
        url = url_getir(self.driver)

        parser = ConfigParser()
        parser.read(path.join(".","config.ini"))

        suffix ="--referrer=https://video.sibnet.ru/ " if  "sibnet" in url else ""
        suffix+= "--msg-level=display-tags=no "
        suffix+="--stream-record={}.mp4 ".format(path.join(".","Kayıtlar",self.bolumler)) if parser.getboolean("TurkAnime","izlerken kaydet") else ""

        system(f'mpv "{url}" {suffix} ')
        return True
