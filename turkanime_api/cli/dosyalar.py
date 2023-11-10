"""
DosyaManager()
    - Config ve izlenenler geçmişi dosyalarını yaratır & düzenler
DownloadGereksinimler()
    - Gereksinimlerin indirilmesini ve paketten çıkarılmasını sağlar.
"""
from os import path,mkdir,replace,rename,remove,system,getcwd
from struct import calcsize
import json
from zipfile import ZipFile
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen
import signal
from shutil import rmtree
from functools import partial
import requests
from py7zr import SevenZipFile

from rich.progress import (
    Event,
    Progress,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,TimeRemainingColumn
)

# yt-dlp, mpv gibi gereksinimlerin indirme linklerinin bulunduğu dosya.
DL_URL="https://raw.githubusercontent.com/KebabLord/turkanime-indirici/master/gereksinimler.json"

class Dosyalar:
    """ Yazılımın konfigürasyon ve indirilenler klasörünü yönet
    - Windows'ta varsayılan dizin: $USER/TurkAnimu
    - Linux'ta varsayılan dizin: /home/$USER/TurkAnimu

    Öznitelikler:
        ayar_path: TurkAnimu config dosyasının dizini
        Dosyalar.gecmis_path: İzlenme ve indirme log'unun dizini
    """
    # Defaults to C:/User/xxx/TurkAnimu veya ~/TurkAnimu dizini.

    def __init__(self):
        self.ta_path = path.join(path.expanduser("~"), "TurkAnimu" )
        if path.isdir(".git"): # Git reposundan çalıştırılıyorsa.
            self.ta_path = getcwd()
        self.ayar_path = path.join(self.ta_path, "ayarlar.json")
        self.gecmis_path = path.join(self.ta_path, "gecmis.json")
        default_ayarlar = {
            "manuel fansub" : False,
            "izlerken kaydet" : False,
            "indirilenler" : ".",
            "izlendi ikonu" : True,
            "aynı anda indirme sayısı" : 3,
        }
        # Gerekli dosyalar eğer daha önce yaratılmadıysa yarat.
        if not path.isdir(".git") and not path.isdir(self.ta_path):
            mkdir(self.ta_path)
        # Yeni ayarlar varsa sistemdekine ekle.
        if path.isfile(self.ayar_path):
            ayarlar = self.ayarlar
            for ayar,value in default_ayarlar.items():
                if not ayar in ayarlar:
                    ayarlar[ayar] = value
        else:
            with open(self.ayar_path,"w",encoding="utf-8") as fp:
                fp.write('{}')
            self.set_ayar(ayar_list=default_ayarlar)
        if not path.isfile(self.gecmis_path):
            with open(self.gecmis_path,"w",encoding="utf-8") as fp:
                fp.write('{"izlendi":{},"indirildi":{}}\n')

    def set_gecmis(self, seri,bolum,islem):
        with open(self.gecmis_path,"r",encoding="utf-8") as f:
            gecmis = json.load(f)
        if not seri in gecmis[islem]:
            gecmis[islem][seri] = []
        if bolum in gecmis[islem][seri]:
            return
        gecmis[islem][seri].append(bolum)
        with open(self.gecmis_path,"w",encoding="utf-8") as f:
            json.dump(gecmis,f,indent=2)

    def set_ayar(self, ayar = None, deger = None, ayar_list = None):
        assert (ayar != None and deger != None) or ayar_list != None
        ayarlar = self.ayarlar
        if ayar_list:
            for n,v in ayar_list.items():
                ayarlar[n] = v
        else:
            ayarlar[ayar] = deger
        with open(self.ayar_path,"w",encoding="utf-8") as fp:
            json.dump(ayarlar,fp,indent=2)

    @property
    def ayarlar(self):
        with open(self.ayar_path,encoding="utf-8") as fp:
            return json.load(fp)

    @property
    def gecmis(self):
        with open(self.gecmis_path,encoding="utf-8") as fp:
            return json.load(fp)



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
        self.bulunmayan=bulunmayan
        self.fetch_gereksinim()

    def fetch_gereksinim(self):
        """ Parse gereksinimler.json """
        if path.isfile("gereksinimler.json"):
            with open("gereksinimler.json") as f:
                gereksinimler = json.load(f)
        else:
            gereksinimler = json.loads(requests.get(DL_URL).text)
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
                    path.join(Dosyalar.ta_path,file["name"]+".exe")
                )
                rmtree("tmp_"+file["name"],ignore_errors=True)
                remove(output)
            if file["type"] == "zip":
                with ZipFile(output, 'r') as zipf:
                    zipf.extractall("tmp_"+file["name"])
                rename(
                    path.join("tmp_"+file["name"],file["name"]+".exe"),
                    path.join(Dosyalar.ta_path,file["name"]+".exe")
                )
                rmtree("tmp_"+file["name"],ignore_errors=True)
                remove(output)
            if file["type"] == "exe":
                if file["is_setup"]:
                    system(output)
                else:
                    replace(output,path.join(Dosyalar.ta_path,file["name"]+".exe"))

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
        except Exception as err:
            self.prog.console.log("HATA:",str(err))
            self.status=False
            return
        self.prog.console.log(f"İndirildi: {dlpath}")

    def download(self, urls, dest_dir):
        """Birden fazla url'yi hedef dosyaya indir."""
        urls = [urls] if not isinstance(urls,list) else urls
        with self.prog:
            with ThreadPoolExecutor(max_workers=3) as pool:
                for url in urls:
                    filename = url.split("/")[-1]
                    dest_path = path.join(dest_dir, filename)
                    task_id = self.prog.add_task("download", filename=filename, start=False)
                    pool.submit(self.copy_url, task_id, url, dest_path)
