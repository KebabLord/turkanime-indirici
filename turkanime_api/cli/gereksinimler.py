from os import path,system,name
from shutil import move
import sys
import tempfile
import re
import subprocess as sp
import json
from zipfile import ZipFile
from py7zr import SevenZipFile
import requests
import questionary as qa

from .dosyalar import Dosyalar
from .cli_tools import CliStatus,DownloadCLI

DL_URL = "https://raw.githubusercontent.com/KebabLord/turkanime-indirici/master/gereksinimler.json"
DEPENDS = ["geckodriver","yt-dlp","mpv"]

NOT_WORKING = -1
MISSING = 0
SUCCESS = 1

class Gereksinimler:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Dosyalar().ta_path
        self._url_liste = None
        self._eksikler = []

    def app_kontrol(self,app):
        """ Gereksinimi çalıştırmayı deneyip exit kodunu öğren. """
        process = sp.Popen(f'{app} --version', stdout=sp.PIPE, stderr=sp.PIPE, shell=True)
        exit_code, stdout = process.wait(), process.stdout.read().decode()
        if exit_code == 0:
            return SUCCESS
        if exit_code in (1,127,32512):
            return MISSING
        return NOT_WORKING

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
            self._url_liste = json.loads(requests.get(DL_URL).text)
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
        """ 7z, Zip veya Exe formatındaki indirilmiş dosyayı uygulama dizinine kurar. """
        file_type = file_path.split(".")[-1]
        tmp = tempfile.TemporaryDirectory()
        if is_dir: # Klasörü kopyala
            from_ = tmp.name
            to_ = path.join(self.folder, file_name.removesuffix("."+file_type))
        else: # Klasörün içindeki dosyayı kopyala
            from_ = path.join(tmp.name, file_name)
            to_ = path.join(self.folder, file_name)

        if file_type == "7z":
            with SevenZipFile(file_path, mode='r') as szip:
                szip.extractall(path=tmp.name)
            move( from_, to_)
        elif file_type == "zip":
            with ZipFile(file_path, 'r') as zipf:
                zipf.extractall(tmp.name)
            move( from_, to_)
        elif file_type == "exe":
            if is_setup:
                system(file_path)
            else:
                move( file_path, to_)


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
