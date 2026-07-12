"""
DosyaManager()
    - Config ve izlenenler geçmişi dosyalarını yaratır & düzenler
DownloadGereksinimler()
    - Gereksinimlerin indirilmesini ve paketten çıkarılmasını sağlar.
"""
from os import path,mkdir,getcwd,replace,fsync
from tempfile import NamedTemporaryFile
from copy import deepcopy
import json
from json import JSONDecodeError

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
    default_ayarlar = {
        "manuel fansub" : False,
        "izlerken kaydet" : False,
        "indirilenler" : ".",
        "izlendi ikonu" : True,
        "paralel indirme sayisi" : 3,
        "max resolution" : False,
        "dakika hatirla" : True,
        "aria2c kullan" : False,
        "AnimeDepo kullanmaya zorla" : False,
        "player önceliği" : None
    }
    default_gecmis = {"izlendi":{},"indirildi":{},"last":None}

    def __init__(self):
        self.ta_path = path.join(path.expanduser("~"), "TurkAnimu" )
        if path.isdir(".git"): # Git reposundan çalıştırılıyorsa.
            self.ta_path = getcwd()
        self.ayar_path = path.join(self.ta_path, "ayarlar.json")
        self.gecmis_path = path.join(self.ta_path, "gecmis.json")
        # Gerekli dosyalar eğer daha önce yaratılmadıysa yarat.
        if not path.isdir(".git") and not path.isdir(self.ta_path):
            mkdir(self.ta_path)
        # Yeni ayarlar varsa sistemdekine ekle.
        if path.isfile(self.ayar_path):
            ayarlar = self.ayarlar
            for ayar,value in self.default_ayarlar.items():
                if not ayar in ayarlar:
                    self.set_ayar(ayar,value)
        else:
            self._write_json(self.ayar_path,self.default_ayarlar)
        if not path.isfile(self.gecmis_path):
            self._write_json(self.gecmis_path,self.default_gecmis)

    def _backup_bozuk(self, file_path):
        backup_path = file_path + ".bozuk"
        i = 1
        while path.exists(backup_path):
            backup_path = f"{file_path}.bozuk.{i}"
            i += 1
        replace(file_path,backup_path)

    def _read_json(self, file_path, default): # JSON bozuksa yedekle, default'u restore et.
        try:
            with open(file_path,encoding="utf-8") as fp:
                return json.load(fp)
        except (JSONDecodeError, OSError):
            if path.exists(file_path):
                self._backup_bozuk(file_path)
            data = deepcopy(default)
            self._write_json(file_path,data)
            return data

    def _write_json(self, file_path, data): # JSON'u tmp dosyaya yazıp orjinali ile replace.
        folder = path.dirname(file_path)
        with NamedTemporaryFile("w",encoding="utf-8",delete=False,dir=folder) as fp:
            tmp_path = fp.name
            json.dump(data,fp,indent=2)
            fp.write("\n")
            fp.flush()
            fsync(fp.fileno())
        replace(tmp_path,file_path)

    def set_gecmis(self, seri,bolum,islem):
        gecmis = self.gecmis
        islem_gecmisi = gecmis.setdefault(islem,{})
        if not seri in islem_gecmisi:
            islem_gecmisi[seri] = []
        if bolum in islem_gecmisi[seri]:
            return
        islem_gecmisi[seri].append(bolum)
        self._write_json(self.gecmis_path,gecmis)

    def set_last_anime(self, slug, title):
        gecmis = self.gecmis
        gecmis["last"] = {"slug":slug,"title":title}
        self._write_json(self.gecmis_path,gecmis)

    def set_ayar(self, ayar = None, deger = None, ayar_list = None):
        assert ayar != None or ayar_list != None
        ayarlar = self.ayarlar
        if ayar_list:
            for n,v in ayar_list.items():
                ayarlar[n] = v
        else:
            ayarlar[ayar] = deger
        self._write_json(self.ayar_path,ayarlar)

    @property
    def ayarlar(self):
        return self._read_json(self.ayar_path,self.default_ayarlar)

    @property
    def gecmis(self):
        gecmis = self._read_json(self.gecmis_path,self.default_gecmis)
        for islem in self.default_gecmis:
            if not islem in gecmis:
                gecmis[islem] = deepcopy(self.default_gecmis[islem])
        return gecmis

    @property
    def last_anime(self):
        last = self.gecmis.get("last")
        return last if isinstance(last,dict) else None
