from os import system,path,mkdir,environ,name
from time import sleep
import json
from bs4 import BeautifulSoup as bs4
from rich import print as rprint

from .players import url_getir
from .dosyalar import DosyaManager
from .tools import create_progress

from time import perf_counter, sleep
from subprocess import Popen, TimeoutExpired
import subprocess
import shlex
import threading

class AnimeSorgula():
    """ İstenilen bölümü veya bölümleri dict olarak getir. """
    def __init__(self,driver=None):
        self.driver=driver
        self.anime_ismi=None
        self.tamliste=None
        self.son_bolum=None
        self.dosya=DosyaManager()

    def get_seriler(self):
        """ Sitedeki tüm animeleri [{name:*,value:*}..] formatında döndürür. """
        with create_progress() as progress:
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
        with create_progress() as progress:
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
            print(" "*50+f"\r\n{i+1}. video indiriliyor:")
            otosub = bool(len(self.bolumler)==1 and self.otosub)
            url = url_getir(bolum,self.driver,manualsub=otosub)
            if not url:
                rprint("[red]Bu fansuba veya bölüme ait çalışan bir player bulunamadı.[/red]")
                sleep(3)
                continue
            suffix="--referer https://video.sibnet.ru/" if "sibnet" in url else ""
            output = path.join(dlfolder,self.seri,bolum)
            system(f'youtube-dl --no-warnings -o "{output}.%(ext)s" "{url}" {suffix}')
            self.dosya.update_gecmis(self.seri,bolum,islem="indirildi")
        return True
    
    def multi_indir(self, worker_count = 2):
        self.dosya.tazele()
        dlfolder = self.dosya.ayar.get("TurkAnime","indirilenler")

        if not path.isdir(path.join(dlfolder,self.seri)):
            mkdir(path.join(dlfolder,self.seri))

        def find_urls(i, bolum):
            print(" "*50+f"\r\n{i+1}. video indiriliyor:")
            otosub = bool(len(self.bolumler)==1 and self.otosub)
            url = url_getir(bolum,self.driver,manualsub=otosub)
            if not url:
                rprint("[red]Bu fansuba veya bölüme ait çalışan bir player bulunamadı.[/red]")
                sleep(3)
                return
            suffix="--referer https://video.sibnet.ru/" if "sibnet" in url else ""
            output = path.join(dlfolder,self.seri,bolum)
            cmd = f'youtube-dl --no-warnings -o "{output}.%(ext)s" "{url}" {suffix}'
            return bolum, cmd

        def thread(bolum, cmd):
            p = Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            while p.poll() is None:
                pass
            print("done => ", bolum)
            self.dosya.update_gecmis(self.seri, bolum,islem="indirildi")
            return True
        
        cmds = []
        for i, bolum in enumerate(self.bolumler):
            cmds.append(find_urls(i, bolum))
        
        queue = [threading.Thread(target=thread, args=(bolum, cmd)) for bolum, cmd in cmds]
        start = perf_counter()
        for thread in queue:
            thread.start()

        for thread in queue:
            thread.join()
        end = perf_counter()

        rprint(f'time took {end - start}')
        sleep(50)
        return True
    
    def oynat(self):
        url = url_getir(self.bolumler,self.driver,manualsub=self.otosub)

        if not url:
            rprint("[red]Bu bölüme ait çalışan bir player bulunamadı.[/red]")
            return False

        suffix ="--referrer=https://video.sibnet.ru/ " if  "sibnet" in url else ""
        suffix+= "--msg-level=display-tags=no "
        if self.dosya.ayar.getboolean("TurkAnime","izlerken kaydet"):
            output = path.join(self.dosya.ROOT,"Kayıtlar",self.bolumler)
            suffix+=f"--stream-record={output}.mp4 "
        system(f'mpv "{url}" {suffix} ')
        self.dosya.update_gecmis(self.seri,self.bolumler,islem="izlendi")
        return True
