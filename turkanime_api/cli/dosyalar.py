"""
DosyaManager()
    - Config ve izlenenler geçmişi dosyalarını yaratır & düzenler
DownloadGereksinimler()
    - Gereksinimlerin indirilmesini ve paketten çıkarılmasını sağlar.
"""
from os import path,mkdir,getcwd
from tempfile import NamedTemporaryFile
from shutil import move
import json

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
        # Ayar isimleri ascii karakterlerden oluşmalı.
        default_ayarlar = {
            "manuel fansub" : False,
            "izlerken kaydet" : False,
            "indirilenler" : ".",
            "izlendi ikonu" : True,
            "paralel indirme sayisi" : 3,
            "max resolution" : True,
            "dakika hatirla" : True,
        }
        # Gerekli dosyalar eğer daha önce yaratılmadıysa yarat.
        if not path.isdir(".git") and not path.isdir(self.ta_path):
            mkdir(self.ta_path)
        # Yeni ayarlar varsa sistemdekine ekle.
        if path.isfile(self.ayar_path):
            ayarlar = self.ayarlar
            for ayar,value in default_ayarlar.items():
                if not ayar in ayarlar:
                    self.set_ayar(ayar,value)
        else:
            with open(self.ayar_path,"w",encoding="utf-8") as fp:
                fp.write('{}')
            self.set_ayar(ayar_list=default_ayarlar)
        if not path.isfile(self.gecmis_path):
            with open(self.gecmis_path,"w",encoding="utf-8") as fp:
                fp.write('{"izlendi":{},"indirildi":{}}\n')

    def set_gecmis(self, seri,bolum,islem):
        with open(self.gecmis_path,"r",encoding="utf-8") as fp:
            gecmis = json.load(fp)
        if not seri in gecmis[islem]:
            gecmis[islem][seri] = []
        if bolum in gecmis[islem][seri]:
            return
        gecmis[islem][seri].append(bolum)
        # Geçmiş dosyasını /tmp'de güncelle, sonra taşı.
        with NamedTemporaryFile("w",encoding="utf-8",delete=False) as tmp:
            with tmp.file as fp:
                json.dump(gecmis,fp,indent=2)
        move(tmp.name,self.gecmis_path)

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
