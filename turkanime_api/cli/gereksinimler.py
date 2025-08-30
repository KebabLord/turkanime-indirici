from os import path,system,name,listdir
from shutil import move
import sys
import tempfile
import re
import subprocess as sp
import json
import platform
import os
from zipfile import ZipFile
from py7zr import SevenZipFile
import requests
import questionary as qa

from .dosyalar import Dosyalar
from .cli_tools import CliStatus,DownloadCLI

DL_URL = "https://raw.githubusercontent.com/KebabLord/turkanime-indirici/master/gereksinimler.json"
DEPENDS = ["yt-dlp","mpv","aria2c"]

NOT_WORKING = -1
MISSING = 0
SUCCESS = 1

class Gereksinimler:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Dosyalar().ta_path
        self._url_liste = None
        self._eksikler = []
        self._platform = self._get_platform()
        self._arch = self._get_arch()

    def _get_platform(self):
        """Mevcut platformu tespit et."""
        system = platform.system().lower()
        if system == "windows":
            return "windows"
        elif system == "linux":
            return "linux"
        elif system == "darwin":
            return "macos"
        else:
            return "unknown"

    def _get_arch(self):
        """Mevcut mimariyi tespit et."""
        machine = platform.machine().lower()
        if machine in ["x86_64", "amd64"]:
            return "x64"
        elif machine in ["i386", "i686"]:
            return "x32"
        elif machine in ["arm64", "aarch64"]:
            return "arm64"
        else:
            return "x64"  # fallback

    def app_kontrol(self,app):
        """ Gereksinimi çalıştırmayı deneyip exit kodunu öğren. """
        try:
            process = sp.Popen(f'{app} --version', stdout=sp.PIPE, stderr=sp.PIPE, shell=True)
            exit_code = process.wait()
            stdout = process.stdout.read().decode() if process.stdout else ""
            if exit_code == 0:
                return SUCCESS
            if exit_code in (1,127,32512):
                return MISSING
            return NOT_WORKING
        except Exception:
            return MISSING

    @property
    def eksikler(self):
        """ Bulunamayan veya çalıştırılamayan gereksinimleri tespit et. """
        if self._eksikler == []:
            for gereksinim in DEPENDS:
                exit_code = self.app_kontrol(gereksinim)
                if exit_code != SUCCESS:
                    if self.app_kontrol(gereksinim) is SUCCESS:
                        continue
                    self._eksikler.append((gereksinim,exit_code))
        return self._eksikler

    @property
    def url_liste(self):
        """ İndirme linklerinin bulunduğu Json dosyasını Dict olarak döndürür """
        if self._url_liste is None:
            try:
                response = requests.get(DL_URL)
                response.raise_for_status()
                raw_data = json.loads(response.text)

                # Yeni formatı eski formata dönüştür
                converted_data = []
                for item in raw_data:
                    if "platforms" in item:
                        # Yeni format - platform bilgisine göre URL seç
                        platform_data = item["platforms"].get(self._platform, {})
                        url = platform_data.get(self._arch, platform_data.get("x64", ""))

                        if url:
                            converted_item = {
                                "name": item["name"],
                                "type": item["type"],
                                "is_setup": item.get("is_setup", False),
                                "url": url
                            }
                            converted_data.append(converted_item)
                    else:
                        # Eski format - doğrudan kullan
                        converted_data.append(item)

                self._url_liste = converted_data
            except Exception as e:
                print(f"Gereksinimler listesi alınamadı: {e}")
                self._url_liste = []
        return self._url_liste

    def otomatik_indir(self, url_liste=None, break_on_fail = False, callback = None):
        """ Tüm eksik dosyaları otomatik olarak indir. """
        fail = []
        url_liste = self.url_liste if url_liste is None else url_liste
        for eksik, _ in self.eksikler:
            meta = next(i for i in url_liste if i['name'] == eksik)
            assert meta is not None
            res = self.dosya_indir(meta["url"],callback=callback)
            if "err_msg" in res:
                fail += [{"name":eksik,"err_msg":res["err_msg"]}]
                if break_on_fail:
                    break
                continue
            self.dosyayi_kur(eksik+".exe",res["path"])
            ec = self.app_kontrol(eksik)
            if ec != SUCCESS:
                fail += [{"name":eksik,"ext_code":ec}]
        return fail

    def dosya_indir(self,url,callback = None):
        """ URL'deki dosyayı indirir, belirtilmişse callback'e rapor eder. """
        remote_file = url.split("/")[-1]
        file_name = path.join(self.tmp.name, remote_file)
        response = requests.get(url, stream=True)
        if response.status_code != 200:
            text = re.sub(" {2,6}"," ",re.sub("<.*?>","",response.text.replace("\n"," ")))
            return {"err_msg": text}
        total_size = int(response.headers.get('content-length', 0))
        chunk_size, downloaded_size = 1024, 0
        with open(file_name, 'wb') as file:
            for data in response.iter_content(chunk_size=chunk_size):
                file.write(data)
                downloaded_size += len(data)
                if callback:
                    hook = {"current":downloaded_size,"total":total_size,"file":remote_file}
                    callback(hook)
        return {"path":file_name}

    def dosyayi_kur(self,file_name,file_path,is_setup=False,is_dir=False):
        """ 7z, Zip, Tar.xz veya Exe formatındaki indirilmiş dosyayı uygulama dizinine kurar. """
        file_type = file_path.split(".")[-1].lower()
        tmp = tempfile.TemporaryDirectory()

        if is_dir: # Klasörü kopyala
            from_ = tmp.name
            to_ = path.join(self.folder, file_name.removesuffix("."+file_type))
        else: # Klasörün içindeki dosyayı kopyala
            from_ = path.join(tmp.name, file_name)
            to_ = path.join(self.folder, file_name)

        try:
            if file_type == "7z":
                with SevenZipFile(file_path, mode='r') as szip:
                    szip.extractall(path=tmp.name)
            elif file_type == "zip":
                with ZipFile(file_path, 'r') as zipf:
                    zipf.extractall(tmp.name)
            elif file_type in ["xz", "gz", "bz2"]:
                # Tar.xz, tar.gz gibi sıkıştırılmış dosyalar için
                import tarfile
                with tarfile.open(file_path, 'r:*') as tar:
                    tar.extractall(tmp.name)
            elif file_type == "exe":
                if is_setup:
                    system(file_path)
                else:
                    move(file_path, to_)
                return

            # Dosya yolunu kontrol et ve taşı
            if not path.exists(from_):
                # Bazı arşivlerde dosya farklı bir yerde olabilir
                extracted_files = []
                for root, dirs, files in os.walk(tmp.name):
                    for file in files:
                        if file == file_name or file_name in file:
                            extracted_files.append(path.join(root, file))

                if extracted_files:
                    from_ = extracted_files[0]
                else:
                    # İlk dosyayı kullan
                    all_files = []
                    for root, dirs, files in os.walk(tmp.name):
                        for file in files:
                            all_files.append(path.join(root, file))
                    if all_files:
                        from_ = all_files[0]
                        file_name = path.basename(from_)

            if path.exists(from_):
                move(from_, path.join(self.folder, file_name))

        except Exception as e:
            print(f"Dosya kurulumu başarısız: {e}")
            return False
        return True


def gereksinim_kontrol_cli():
    """ Gereksinimleri kontrol eder ve gerekirse indirip kurar."""
    gerek = Gereksinimler()
    with CliStatus("Gereksinimler kontrol ediliyor.."):
        eksikler = gerek.eksikler
    if eksikler:
        eksik_msg = ""
        guide_msg = "\nManuel indirmek için:\nhttps://github.com/KebabLord/turkanime-indirici/wiki"
        for eksik,exit_code in eksikler:
            if exit_code is MISSING:
                eksik_msg += f"!) {eksik} yazılımı bulunamadı.\n"
            else:
                eksik_msg += f"!) {eksik} yazılımı bulundu ancak çalıştırılamadı.\n"
        print(eksik_msg,end="\n\n")
        if name=="nt" and qa.confirm("Otomatik kurulsun mu?").ask():
            with CliStatus("Güncel indirme linkleri getiriliyor.."):
                links = gerek.url_liste
            dl_cli = DownloadCLI()
            with dl_cli.progress:
                fails = gerek.otomatik_indir(url_liste=links, callback=dl_cli.dl_callback)
            eksik_msg = ""
            for fail in fails:
                if "err_msg" in fail:
                    eksik_msg += f"!) {fail['name']} indirilemedi\n"
                    if fail["err_msg"] != "":
                        eksik_msg += f" - {fail['err_msg'][:55]}...\n"
                elif "ext_code" in fail:
                    if fail["ext_code"] is MISSING:
                        eksik_msg += f"!) {fail['name']} kurulamadı.\n"
                    else:
                        eksik_msg += f"!) {fail['name']} çalıştırılamadı.\n"
            if fails:
                print(eksik_msg + guide_msg)
                input("\n(ENTER'a BASIN)")
                sys.exit(1)
        else:
            print(guide_msg)
            input("\n(ENTER'a BASIN)")
            sys.exit(1)
