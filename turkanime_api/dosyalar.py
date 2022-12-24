"""
DosyaManager()
    - Config ve izlenenler geçmişi dosyalarını yaratır & düzenler
DownloadGereksinimler()
    - Gereksinimlerin indirilmesini ve paketten çıkarılmasını sağlar.
"""
from os import path,mkdir,replace,rename,remove,system
from struct import calcsize
from configparser import ConfigParser
import json
from py7zr import SevenZipFile
from zipfile import ZipFile
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen
import signal
from shutil import rmtree
from functools import partial
import requests

from rich.progress import (
    Event,
    Progress,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,TimeRemainingColumn
)


class DosyaManager():
    """ Yazılımın konfigürasyon ve indirilenler klasörünü yönet
    - Windows'ta varsayılan dizin: Belgelerim/TurkAnimu
    - Linux'ta varsayılan dizin: /home/$USER/TurkAnimu
    """
    def __init__(self):
        if path.isdir(".git"): # Git reposundan çalıştırıldığında.
            self.ROOT = "."
        else: # Pip modülü veya Exe olarak çalıştırıldığında.
            self.ROOT = path.join(path.expanduser("~"), "TurkAnimu" )

        self.default = {
            "manuel fansub" : "False",
            "izlerken kaydet" : "False",
            "indirilenler" : ".",
            "izlendi ikonu" : "True"
        }
        self.ayar_path = path.join(self.ROOT, "ayarlar.ini")
        self.gecmis_path = path.join(self.ROOT, "gecmis.json")
        self.verify_dosyalar()
        self.ayar = ConfigParser()
        self.ayar.read(self.ayar_path)

    def tazele(self):
        self.ayar = ConfigParser()
        self.ayar.read(self.ayar_path)

    def save_ayarlar(self):
        with open(self.ayar_path,"w") as f:
            self.ayar.write(f)
        self.tazele()

    def verify_dosyalar(self):
        """ Config dosyasını güncelle & yoksa yarat. """
        if not path.isdir(".git"):
            if not path.isdir(self.ROOT):
                mkdir(self.ROOT)
            # Eski sürüme ait config dosyasını yeni ana dizine taşı
            olds = ["TurkAnime.ini",path.join("TurkAnimu","TurkAnime.ini"),"config.ini"]
            for old in olds:
                old = path.join(path.expanduser("~"),old)
                if path.isfile(old):
                    replace(old,self.ayar_path)

        if not path.isfile(self.ayar_path):
            new = "[TurkAnime]\n"
            for key,val in self.default.items():
                new += f"{key} = {val}\n"
            with open(self.ayar_path,"w") as f:
                f.write(new)
        else:
            # Önceki sürümlere ait config'e yeni ayarları ekle
            cfg = ConfigParser()
            cfg.read(self.ayar_path)
            for key,val in self.default.items():
                if key in cfg.options("TurkAnime"):
                    continue
                cfg.set('TurkAnime',key,val)
            with open(self.ayar_path,"w") as f:
                cfg.write(f)
        if not path.isfile(self.gecmis_path):
            with open(self.gecmis_path,"w") as f:
                f.write('{"izlendi":{},"indirildi":{}}\n')

    def update_gecmis(self,seri,bolum,islem):
        with open(self.gecmis_path,"r") as f:
            gecmis = json.load(f)
        if not seri in gecmis[islem]:
            gecmis[islem][seri] = []
        if bolum in gecmis[islem][seri]:
            return
        gecmis[islem][seri].append(bolum)
        with open(self.gecmis_path,"w") as f:
            json.dump(gecmis,f,indent=2)


class DownloadGereksinimler():
    """ Gereksinimleri indirir, arşivden çıkarır ve gerekirse kurar. """
    def __init__(self,bulunmayan=[]):
        self.done_event = Event()
        signal.signal(signal.SIGINT, lambda s,f:self.done_event.set())
        self.prog = Progress(
            TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
            BarColumn(bar_width=None),"[self.prog.percentage]{task.percentage:>3.1f}%",
            "•",DownloadColumn(),"•",TransferSpeedColumn(),"•",TimeRemainingColumn()
        )
        self.status = True
        self.dosya = DosyaManager()
        self.bulunmayan=bulunmayan
        self.fetch_gereksinim()

    def fetch_gereksinim(self):
        """ Parse gereksinimler.json """
        if path.isfile("gereksinimler.json"):
            with open("gereksinimler.json") as f:
                gereksinimler = json.load(f)
        else:
            base_url="https://raw.githubusercontent.com/KebabLord/turkanime-indirici/master/gereksinimler.json"
            gereksinimler = json.loads(requests.get(base_url).text)
        arch = calcsize("P")*8

        for file in gereksinimler:
            if not file["name"] in self.bulunmayan:
                continue
            url = file["url_x32"] if "url_x32" in file and arch == 32 else file["url"]
            output = url.split("/")[-1]
            if not path.isfile(output):
                self.download(url,".")

            if not self.status:
                self.prog.stop()
                self.prog.console.log(
                    "\n\nSiteye ulaşılamıyor: https://"+file["url"].split("/")[2]+
                    "\nGereksinimleri manuel olarak kurmak için klavuz.html'i oku.")
                exit(1)


            if file["type"] == "7z":
                szip = SevenZipFile(output,mode='r')
                szip.extractall(path="tmp_"+file["name"])
                szip.close()
                rename(
                    path.join("tmp_"+file["name"],file["name"]+".exe"),
                    path.join(self.dosya.ROOT,file["name"]+".exe")
                )
                rmtree("tmp_"+file["name"],ignore_errors=True)
                remove(output)
            if file["type"] == "zip":
                with ZipFile(output, 'r') as zipf:
                    zipf.extractall("tmp_"+file["name"])
                rename(
                    path.join("tmp_"+file["name"],file["name"]+".exe"),
                    path.join(self.dosya.ROOT,file["name"]+".exe")
                )
                rmtree("tmp_"+file["name"],ignore_errors=True)
                remove(output)
            if file["type"] == "exe":
                if file["is_setup"]:
                    system(output)
                else:
                    replace(output,path.join(self.dosya.ROOT,file["name"]+".exe"))

    def copy_url(self, task_id, url, dlpath):
        """Copy data from a url to a local file."""
        self.prog.console.log(f"İndiriliyor {url.split('/')[-1]}")
        try:
            response = urlopen(url)
        except Exception as err:
            self.prog.console.log("HATA:",str(err))
            self.status=False
            return
        try:
            # This will break if the response doesn't contain content length
            self.prog.update(task_id, total=int(response.info()["Content-length"]))
            with open(dlpath, "wb") as dest_file:
                self.prog.start_task(task_id)
                for data in iter(partial(response.read, 32768), b""):
                    dest_file.write(data)
                    self.prog.update(task_id, advance=len(data))
                    if self.done_event.is_set():
                        print("Başarısız")
                        return
        except Exception as rr:
            self.prog.console.log("HATA:",str(err))
            self.status=False
            return
        self.prog.console.log(f"İndirildi: {dlpath}")

    def download(self, urls, dest_dir):
        """Birden fazla url'yi hedef dosyaya indir."""
        urls = [urls] if not type(urls) is list else urls
        with self.prog:
            with ThreadPoolExecutor(max_workers=3) as pool:
                for url in urls:
                    filename = url.split("/")[-1]
                    dest_path = path.join(dest_dir, filename)
                    task_id = self.prog.add_task("download", filename=filename, start=False)
                    pool.submit(self.copy_url, task_id, url, dest_path)
