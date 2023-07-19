import re

class Anime:
    """
    Bir anime serisi hakkında her verinin bulunduğu obje.
    Obje'yi yaratmak için animenin kodu veya URL'si yeterlidir.

    Öznitelikler:
    - slug: Animenin kodu: "non-non-biyori".
    - title: Animenin okunaklı ismi, örneğin: Non Non Biyori
    - anime_id: Animenin türkanime id'si. Bölümleri ve anime resmini getirirken gerekli.
    - bolumler_data: Anime bölümlerinin [(str:slug,str:isim),] formatında listesi.
    - bolumler: Anime bölümlerinin [Bolum:bolum1,Bolum:bolum2,] formatında obje listesi.
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
        req = self.driver.execute_script(f"return $.get('/anime/{self.slug}')")
        twitmeta = re.findall(r'twitter.image" content="(.*?serilerb/(.*?)\.jpg)"',req)[0]
        self.info["Resim"], self.anime_id = twitmeta
        if not self.title:
            self.title = re.findall(r'<title>(.*?)<\/title>',req).pop()

        # Anime sayfasındaki bilgi tablosunu parse'la
        info_table=re.findall(r'<div id="animedetay">(<table.*?</table>)',req)[0]
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
            req = self.driver.execute_script(f"return $.get('/ajax/bolumler&animeId={anime_id}')")
            self._bolumler_data = re.findall(r'\/video\/(.*?)\\?".*?title=.*?"(.*?)\\?"',req)
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
        req = self.html
        # Yalnızca tek bir fansub varsa
        if not re.search(".*birden fazla grup",req):
            fansub = re.findall(r"</span> ([^\\<>]*)</button>.*?iframe",req)[0]
            vids=re.findall(r"(ajax\/videosec&b=[A-Za-z0-9]+&v=.*?)'.*?<\/span> ?(.*?)<\/button",req)
            for vpath,player in vids:
                self._videos.append(Video(self,vpath,player,fansub))
        # Fansublar da parse'lanacaksa
        elif parse_fansubs:
            fansubs = re.findall(r"(ajax\/videosec&.*?)(?=').*?<\/span> ?(.*?)<\/a>",req)
            for path,fansub in fansubs:
                r = self.driver.execute_script(f'return $.get("{path}")')
                vids=re.findall(r"(ajax\/videosec&b=[A-Za-z0-9]+&v=.*?)'.*?<\/span> ?(.*?)<\/button",r)
                for vpath,player in vids:
                    self._videos.append(Video(self,vpath,player,fansub))
        # Fansubları parselamaksızın tüm videoları getir
        else:
            allpath = re.findall(r"(ajax\/videosec&b=[A-Za-z0-9]+.*?)&[fv]=.*?'.*?<\/span>",req)[0]
            r = self.driver.execute_script(f'return $.get("{allpath}")')
            vids=re.findall(r"(ajax\/videosec&b=[A-Za-z0-9]+&v=.*?)'.*?<\/span> ?(.*?)<\/button",r)
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
        self._url = None
        self._download_url = None
        self._resolution = None
        self._size = None
    ...
