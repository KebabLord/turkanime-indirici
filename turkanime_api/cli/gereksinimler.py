from os import path,replace,system
import tempfile
import re
import subprocess as sp
import json
from zipfile import ZipFile
from py7zr import SevenZipFile
import requests

from .dosyalar import Dosyalar

DL_URL = "https://raw.githubusercontent.com/KebabLord/turkanime-indirici/master/gereksinimler.json"
DEPENDS = ["geckodriver","youtube-dl","mpv"]

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
        exit_code = sp.Popen(
            f'{app} --version',
            stdout=sp.PIPE,
            stderr=sp.PIPE,
            shell=True
        ).wait()
        if exit_code == 0:
            return SUCCESS
        if exit_code in (1,127):
            return MISSING
        return NOT_WORKING

    @property
    def eksikler(self):
        """ Bulunamayan veya çalıştırılamayan gereksinimler. """
        if self._eksikler == []:
            for gereksinim in DEPENDS:
                exit_code = self.app_kontrol(gereksinim)
                if exit_code != SUCCESS:
                    self._eksikler.append((gereksinim,exit_code))
        return self._eksikler

    @property
    def url_liste(self):
        """ İndirme linklerinin bulunduğu Json dosyasını Dict olarak döndürür """
        if self._url_liste is None:
            self._url_liste = json.loads(requests.get(DL_URL).text)
        return self._url_liste

    def otomatik_indir(self, break_on_fail = False, callback = None):
        """ Tüm eksik dosyaları otomatik olarak indir. """
        fail = []
        for eksik, _ in self.eksikler:
            meta = next(i for i in self.url_liste if i['name'] == eksik)
            res = self.dosya_indir(meta["url"],callback=callback)
            if "err_msg" in res:
                fail += [{"name":eksik,"err_msg":res["err_msg"]}]
                if break_on_fail:
                    break
                continue
            self.dosyayi_kur(eksik,res["path"])
            ec = self.app_kontrol(eksik)
            if ec != SUCCESS:
                fail += [{"name":eksik,"ext_code":ec}]
        return fail

    def dosya_indir(self,url,callback = None):
        """ URL'deki dosyayı indirir, belirtilmişse callback'e rapor eder. """
        file_name = path.join(self.tmp, url.split("/")[-1])
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
                    callback(downloaded_size, total_size)
        return {"path":file_name}

    def dosyayi_kur(self,file_name,file_path,setup=False):
        """ 7z, Zip veya Exe formatındaki indirilmiş dosyayı uygulama dizinine kurar. """
        file_type = file_path.split(".")[-1]
        tmp = tempfile.TemporaryDirectory()
        if file_type == "7z":
            with SevenZipFile(file_path, mode='r') as szip:
                szip.extractall(path=tmp.name)
            replace( path.join(tmp.name,file_name), self.folder)
        elif file_type == "zip":
            with ZipFile(file_path, 'r') as zipf:
                zipf.extractall(tmp.name)
            replace( path.join(tmp.name,file_name), path.join(self.folder,file_name))
        elif file_type == "exe":
            if setup:
                system(file_path)
            else:
                replace( path.join(tmp.name,file_name), path.join(self.folder,file_name))
