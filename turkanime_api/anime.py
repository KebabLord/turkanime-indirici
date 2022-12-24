from os import system,path,mkdir,environ,name
import json
from bs4 import BeautifulSoup as bs4
from rich.progress import Progress, BarColumn, SpinnerColumn
from rich import print as rprint

from .players import url_getir
from .dosyalar import DosyaManager

class AnimeSorgula():
    def __init__(self,driver=None):
        self.driver=driver
        self.anime_ismi=None
        self.tamliste=None
        self.son_bolum=None
        self.dosya=DosyaManager()

    def get_seriler(self):
        """ Sitedeki tüm animeleri [{name:*,value:*}..] formatında döndürür. """
        with Progress(SpinnerColumn(), '[progress.description]{task.description}', BarColumn(bar_width=40)) as progress:
            task = progress.add_task("[cyan]Anime listesi getiriliyor..", start=False)
            if self.tamliste:
                progress.update(task,visible=False)
                return self.tamliste.keys()

            soup = bs4(
                self.driver.execute_script("return $.get('/ajax/tamliste')"),
                "html.parser"
            )
            raw_series, self.tamliste = soup.findAll('span',{"class":'animeAdi'}) , {}
            for seri in raw_series:
                self.tamliste[seri.text] = seri.findParent().get('href').split('anime/')[1]
            progress.update(task,visible=False)
            return [seri.text for seri in raw_series]

    def get_bolumler(self, isim):
        """ Animenin bölümlerini {bölüm,title} formatında döndürür. """
        with Progress(SpinnerColumn(), '[progress.description]{task.description}', BarColumn(bar_width=40)) as progress:
            task = progress.add_task("[cyan]Bölümler getiriliyor..", start=False)
            anime_slug=self.tamliste[isim]
            self.anime_ismi = anime_slug
            raw = self.driver.execute_script(f"return $.get('/anime/{anime_slug}')")
            soup = bs4(raw,"html.parser")
            anime_code = soup.find('meta',{'name':'twitter:image'}).get('content').split('lerb/')[1][:-4]

            raw = self.driver.execute_script(f"return $.get('/ajax/bolumler&animeId={anime_code}')")
            soup = bs4(raw,"html.parser")

            bolumler = []
            for bolum in soup.findAll("span",{"class":"bolumAdi"}):
                bolumler.append({
                    'name':bolum.text,
                    'value':bolum.findParent().get("href").split("video/")[1]
                })
            progress.update(task,visible=False)
            return bolumler

    def mark_bolumler(self,slug,bolumler,islem):
        """ İzlenen bölümlere tick koyar. """
        self.dosya.tazele()
        if not self.dosya.ayar.getboolean("TurkAnime","izlendi ikonu"):
            return
        is_watched = lambda ep: slug in gecmis[islem] and ep in gecmis[islem][slug]
        with open(self.dosya.gecmis_path) as f:
            gecmis = json.load(f)
        self.son_bolum=None
        for bolum in bolumler:
            if is_watched(bolum["value"]) and bolum["name"][-2:] != " ●":
                bolum["name"] += " ●"
                self.son_bolum = bolum


class Anime():
    """ İstenilen bölümü veya bölümleri oynat ya da indir. """
    def __init__(self,driver,seri,bolumler):
        self.driver = driver
        self.seri = seri
        self.bolumler = bolumler
        self.dosya = DosyaManager()
        self.otosub = self.dosya.ayar.getboolean("TurkAnime","manuel fansub")
        environ["PATH"] += ";" if name=="nt" else ":" + self.dosya.ROOT

    def indir(self):
        self.dosya.tazele()
        dlfolder = self.dosya.ayar.get("TurkAnime","indirilenler")

        if not path.isdir(path.join(dlfolder,self.seri)):
            mkdir(path.join(dlfolder,self.seri))

        for i,bolum in enumerate(self.bolumler):
            print(" "*50+f"\r\n{i+1}. bölüm indiriliyor:")
            otosub = bool(len(self.bolumler)==1 and self.otosub)
            url = url_getir(bolum,self.driver,manualsub=otosub)
            suffix="--referer https://video.sibnet.ru/" if "sibnet" in url else ""
            system(f'youtube-dl --no-warnings -o "{path.join(dlfolder,self.seri,bolum)}.%(ext)s" "{url}" {suffix}')
            self.dosya.update_gecmis(self.seri,bolum,islem="indirildi")
        return True

    def oynat(self):
        url = url_getir(self.bolumler,self.driver,manualsub=self.otosub)

        if not url:
            rprint("[red]Bu bölüme ait çalışan bir player bulunamadı.[/red]")
            return False

        suffix ="--referrer=https://video.sibnet.ru/ " if  "sibnet" in url else ""
        suffix+= "--msg-level=display-tags=no "
        if self.dosya.ayar.getboolean("TurkAnime","izlerken kaydet"):
            suffix+="--stream-record={}.mp4 ".format(path.join(self.dosya.ROOT,"Kayıtlar",self.bolumler))
        system(f'mpv "{url}" {suffix} ')
        self.dosya.update_gecmis(self.seri,self.bolumler,islem="izlendi")
        return True
