import re
import json
import yt_dlp

from .bypass import get_real_url

class Anime:
    """
    Bir anime serisi hakkında her verinin bulunduğu obje.
    Obje'yi yaratmak için animenin kodu veya URL'si yeterlidir.

    Öznitelikler:
    - slug: Animenin kodu: "non-non-biyori".
    - title: Animenin okunaklı ismi, örneğin: Non Non Biyori
    - anime_id: Animenin türkanime id'si. Bölümleri ve anime resmini getirirken gerekli.
    - bolumler_data: Anime bölümlerinin [(slug:str,isim:str),] formatında listesi.
    - bolumler: Anime bölümlerinin [bolum1:Bolum,bolum2:Bolum,] formatında obje listesi.
    - info: Anime sayfasından parse'lanan özet,kategori,stüdyo gibi meta bilgileri içeren dict.
    """
    def __init__(self,driver,slug):
        self.driver = driver
        self.slug = slug
        self.title = None
        self.anime_id = 0
        self.info = {
            "Kategori":None,
            "Japonca":None,
            "Anime Türü":[],
            "Bölüm Sayısı":0,
            "Başlama Tarihi":None,
            "Bitiş Tarihi":None,
            "Stüdyo":None,
            "Puanı":0.0,
            "Özet":None,
            "Resim":None
        }
        self.fetch_info()
        self._bolumler_data = None
        self._bolumler = []

    def fetch_info(self):
        """Anime detay sayfasını ayrıştır."""
        src = self.driver.execute_script(f"return $.get('/anime/{self.slug}')")
        twitmeta = re.findall(r'twitter.image" content="(.*?serilerb/(.*?)\.jpg)"',src)[0]
        self.info["Resim"], self.anime_id = twitmeta
        if not self.title:
            self.title = re.findall(r'<title>(.*?)<\/title>',src).pop()

        # Anime sayfasındaki bilgi tablosunu parse'la
        info_table=re.findall(r'<div id="animedetay">(<table.*?</table>)',src)[0]
        raw_m = re.findall(r"<tr>.*?<b>(.*?)<\/b>.*?width.*?>(.*?)<\/td>.*?<\/tr>",info_table)
        for key,val in raw_m:
            if not key in self.info:
                continue
            val = re.sub("<.*?>","",val)
            val = re.sub("^ {1,3}","",val)
            if key == "Puanı":
                val = float(re.findall("^(.*?) ",val).pop())
            elif key == "Anime Türü":
                val = val.split("  ")
            self.info[key] = val
        self.info["Özet"] = re.findall('"ozet">(.*?)</p>',info_table)[0]

    @property
    def bolumler_data(self):
        """ Anime bölümlerinin [(slug,isim),] formatında listesi. """
        if self._bolumler_data is None:
            anime_id = self.anime_id
            src = self.driver.execute_script(f"return $.get('/ajax/bolumler&animeId={anime_id}')")
            self._bolumler_data = re.findall(r'\/video\/(.*?)\\?".*?title=.*?"(.*?)\\?"',src)
        return self._bolumler_data

    @property
    def bolumler(self):
        """ Anime bölümlerinin [Bolum,] formatında listesi. """
        if not self._bolumler:
            for slug,title in self.bolumler_data:
                self._bolumler.append(Bolum(self.driver,slug=slug,title=title,anime=self))
        return self._bolumler

    @staticmethod
    def fetch_anime_list():
        print("poop")



class Bolum:
    """
    Bir anime bölum'ünü temsil eden obje.
    Obje'yi yaratmak için bölümün kodu veya URL'si yeterlidir.

    Öznitelikler:
    - slug: Bölümün kodu: "naruto-54-bolum" veya URLsi: "https://turkani.co/video/naruto-54-bolum".
    - title: Bölümün okunaklı ismi. (opsiyonel)
    - anime: Bölümün ait olduğu anime'nin objesi, eğer tanımlanmadıysa erişildiğinde yaratılır.
    """
    def __init__(self,driver,slug,anime=None,title=None):
        if "http" == slug[:4]:
            slug = slug.split("/")[-1]
        self.driver = driver
        self.slug = slug
        self._title = title
        self._html = None
        self._videos = []
        self._anime = anime

    @property
    def html(self):
        if self._html is None:
            self._html = self.driver.execute_script(f'return $.get("/video/{self.slug}")')
        return self._html

    @property
    def title(self):
        if self._title is None:
            self._title = re.findall(r'<title>(.*?)<\/title>',self.html)[0]
        return self._title

    @property
    def videos(self):
        if self._videos == []:
            self.get_videos()
        return self._videos

    @property
    def anime(self):
        """ Bu bölümün ait olduğu anime serisi objesini yarat. """
        if self._anime is None:
            self._anime = "Naruto"
        return self._anime

    def get_videos(self,parse_fansubs=False):
        # Yalnızca tek bir fansub varsa
        if not re.search(".*birden fazla grup",self.html):
            fansub = re.findall(r"</span> ([^\\<>]*)</button>.*?iframe",self.html)[0]
            vids=re.findall(r"(ajax\/videosec&b=[A-Za-z0-9]+&v=.*?)'.*?<\/span> ?(.*?)<\/button",self.html)
            for vpath,player in vids:
                self._videos.append(Video(self,vpath,player,fansub))
        # Fansublar da parse'lanacaksa
        elif parse_fansubs:
            fansubs = re.findall(r"(ajax\/videosec&.*?)'.*?<\/span> ?(.*?)<\/a>",self.html)
            for path,fansub in fansubs:
                src = self.driver.execute_script(f'return $.get("{path}")')
                vids=re.findall(r"(ajax\/videosec&b=[A-Za-z0-9]+&v=.*?)'.*?<\/span> ?(.*?)<\/button",src)
                for vpath,player in vids:
                    self._videos.append(Video(self,vpath,player,fansub))
        # Fansubları parselamaksızın tüm videoları getir
        else:
            allpath = re.findall(r"(ajax\/videosec&b=[A-Za-z0-9]+.*?)&[fv]=.*?'.*?<\/span>",self.html)[0]
            src = self.driver.execute_script(f'return $.get("{allpath}")')
            vids=re.findall(r"(ajax\/videosec&b=[A-Za-z0-9]+&v=.*?)'.*?<\/span> ?(.*?)<\/button",src)
            for vpath,player in vids:
                self._videos.append(Video(self,vpath,player))
        return self._videos



class Video:
    """
    Bir bölüm adına yüklenmiş herhangi bir videoyu temsil eden obje.

    Öznitelikler:
    - path: Video'nun türkanime'deki hash'li dizin yolu.
    - bolum: Video'nun ait olduğu bölüm objesi.
    - fansub: eğer belirtilmişse, videoyu yükleyen fansub'un ismi.
    - url: Videonun decrypted gerçek url'si, örn: https://youtube.com/watch?v=XXXXXXXX
    """
    def __init__(self,bolum,path,player=None,fansub=None):
        self.path = path
        self.player = player
        self.fansub = fansub
        self.bolum = bolum
        self._info = None
        self._url = None

    @property
    def url(self):
        if self._url is None:
            src = self.bolum.driver.execute_script(f"return $.get('{self.path}')")
            # şifreli iframe'in encryption parametreleri: base64('{"ct":*,"iv":*,"s":*}')
            cipher = re.findall(r"\/embed\/#\/url\/(.*?)\?status",src)[0]
            plaintext = get_real_url(self.bolum.driver,cipher)
            # "\\/\\/fembed.com\\/v\\/0d1e8ilg"  -->  "https://fembed.com/v/0d1e8ilg"
            self._url = "https:"+json.loads(plaintext)
        return self._url

    @property
    def info(self):
        if self._info is None:
            ydl_opts = {"quiet":True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self._info = ydl.extract_info(self.url, download=False)
        return self._info

    def indir(self):
        ...

    def oynat(self):
        ...
