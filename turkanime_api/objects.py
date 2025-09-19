""" Örnek:
>>> ani = Anime("non-non-biyori")
>>> bol3 = ani.bolumler[2]
>>> vid1 = bol3.videos[0]
>>> vid1.oynat()
"""
from os import remove
from os.path import join
from tempfile import NamedTemporaryFile
import subprocess as sp
import re
import json
from yt_dlp import YoutubeDL
from yt_dlp.networking.impersonate import ImpersonateTarget

from .bypass import get_real_url, unmask_real_url, fetch, get_alucard_m3u8
from .common.utils import get_platform, get_arch

# Çalıştığı bilinen playerlar ve öncelikleri
SUPPORTED = [
    "YADISK",
    "MAIL",
    "ALUCARD(BETA)",
    "PIXELDRAIN",
    "AMATERASU(BETA)",
    "HDVID",
    "ODNOKLASSNIKI",
    "GDRIVE",
    "MP4UPLOAD",
    "DAILYMOTION",
    "SIBNET",
    "VK",
    "VIDMOLY",
    "YOURUPLOAD",
    "SENDVID",
    "MYVI",
    "UQLOAD",
]

class LogHandler:
    """ TODO: ytdlp log handler prototipi """
    @staticmethod
    def error(msg):
        pass  # msg is unused but required by yt-dlp interface
    @staticmethod
    def warning(msg):
        pass  # msg is unused but required by yt-dlp interface
    @staticmethod
    def debug(msg):
        pass  # msg is unused but required by yt-dlp interface


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
    - parse_fansubs: Bolum objesi yaratılırken fansubları da parse'lamasını belirt.
    """
    def __init__(self,slug,parse_fansubs=True):
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
        self.parse_fansubs = parse_fansubs

    def fetch_info(self):
        """Anime detay sayfasını ayrıştır."""
        src = fetch(f'/anime/{self.slug}')
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

    def get_bolum_listesi(self):
        """ Anime bölümlerinin [(slug,isim),] formatında listesi. """
        anime_id = self.anime_id
        src = fetch(f'/ajax/bolumler&animeId={anime_id}')
        return re.findall(r'\/video\/(.*?)\\?".*?title=.*?"(.*?)\\?"',src)

    @staticmethod
    def get_anime_listesi():
        """ Anime serilerinin [(slug,isim),] formatında listesi. """
        src = fetch("/ajax/tamliste")
        return re.findall(r'\/anime\/(.*?)".*?animeAdi">(.*?)<',src)

    @property
    def bolumler(self):
        """ Anime bölümlerinin [Bolum,] formatında listesi. """
        if not self._bolumler:
            for slug,title in self.get_bolum_listesi():
                self._bolumler.append(
                    Bolum(
                        slug=slug,
                        title=title,
                        anime=self,
                        parse_fansubs=self.parse_fansubs))
        return self._bolumler



class Bolum:
    """
    Bir anime bölum'ünü temsil eden obje.
    Obje'yi yaratmak için bölümün kodu veya URL'si yeterlidir.

    Öznitelikler:
    - slug: Bölümün kodu: "naruto-54-bolum" veya URLsi: "https://turkani.co/video/naruto-54-bolum".
    - title: Bölümün okunaklı ismi. (opsiyonel)
    - anime: Bölümün ait olduğu anime'nin objesi, eğer tanımlanmadıysa erişildiğinde yaratılır.
    - parse_fansubs: Fansubları da parse'la. Fazladan fansub sayısı kadar istek gönderir.
    """
    def __init__(self,slug,anime=None,title=None,parse_fansubs=True):
        if "http" == slug[:4]:
            slug = slug.split("/")[-1]
        self.slug = slug
        self.parse_fansubs = parse_fansubs
        self._title = title
        self._html = None
        self._videos = []
        self._anime = anime
        self._fansubs = []

    @property
    def html(self):
        if self._html is None:
            self._html = fetch(f"/video/{self.slug}")
        return self._html

    @property
    def title(self):
        if self._title is None:
            self._title = re.findall(r'<title>(.*?)<\/title>',self.html)[0]
        return self._title

    @property
    def videos(self):
        if not self._videos:
            self.get_videos()
        return self._videos

    @property
    def anime(self):
        """ Bu bölümün ait olduğu anime serisi objesini yarat. """
        if self._anime is None:
            ...
        return self._anime

    @property
    def fansubs(self):
        """ Bölüm sayfasından fansub listesini ayrıştır. """
        if not self._fansubs:
            self._fansubs = re.findall(r"</span> ([^<>/]*?)</a></button>",self.html)
            if not self._fansubs:
                self._fansubs = re.findall(r"</span> ([^\\<>]*)</button>.*?iframe",self.html)
        return self._fansubs

    def get_videos(self):
        self._videos = []
        # Yalnızca tek bir fansub varsa
        if not re.search(".*birden fazla grup",self.html):
            fansub = re.findall(r"</span> ([^\\<>]*)</button>.*?iframe",self.html)[0]
            vids = re.findall(r"/embed/#/url/(.*?)\?status=0\".*?</span> ([^ ]*?) ?</button>", self.html)
            vids += re.findall(r"(ajax\/videosec&b=[A-Za-z0-9]+&v=.*?)'.*?<\/span> ?(.*?)<\/button",self.html)
            for vpath,player in vids:
                self._videos.append(Video(self,vpath,player,fansub))
        # Fansublar da parse'lanacaksa
        elif self.parse_fansubs:
            fansubs = re.findall(r"(ajax\/videosec&.*?)'.*?<\/span> ?(.*?)<\/a>",self.html)
            for path,fansub in fansubs:
                src = fetch(path)
                vids = re.findall(r"/embed/#/url/(.*?)\?status=0\".*?</span> ([^ ]*?) ?</button>", src)
                vids += re.findall(r"(ajax\/videosec&b=[A-Za-z0-9]+&v=.*?)'.*?<\/span> ?(.*?)<\/button",src)
                for vpath,player in vids:
                    self._videos.append(Video(self,vpath,player,fansub))
        # Fansubları parselamaksızın tüm videoları getir
        else:
            allpath = re.findall(r"(ajax\/videosec&b=[A-Za-z0-9]+.*?)&[fv]=.*?'.*?<\/span>",self.html)[0]
            src = fetch(allpath)
            vids = re.findall(r"/embed/#/url/(.*?)\?status=0\".*?</span> ([^ ]*?) ?</button>", src)
            vids += re.findall(r"(ajax\/videosec&b=[A-Za-z0-9]+&v=.*?)'.*?<\/span> ?(.*?)<\/button",src)
            for vpath,player in vids:
                self._videos.append(Video(self,vpath,player))
        return self._videos

    def best_video(self, by_res=True, by_fansub=None, default_res=600, callback=lambda x: None, early_subset: int = 8):
        """
        Parametrelerde belirtilmiş en ideal videoyu tespit edip döndürür.

        - by_res: 1080p'ye ulaşmaya çalış
        - by_fansub: belirtilen fansub'u öncelikli tut.
        - default_res: Çözünürlüğü bilinmeyen videoların varsayılan çözünürlüğü.
        - callback: function(hook_dict)
        """
        # Yalnızca desteklenenleri filtrele.
        vids = list(filter(lambda x: x.is_supported, self.videos))

        # Callback fonksiyonu belirtilmişse paslanacak hook_dict
        hook_dict = {
            "current": None,
            "total": len(vids),
            "player": None,
            "status": None,
            "object": self
        }

        # Kaliteli player'a göre sırala
        vids = sorted(vids, key = lambda x: SUPPORTED.index(x.player))
        # Seçilmiş fansub'un videolarını öncelikli tut
        if by_fansub:
            vids = sorted(vids, key = lambda x: x.fansub != by_fansub)

        # 1080p seçim hızlandırma: çözünürlükleri paralel önbellekle
        # İlk etapta oyuncu önceliğine göre ilk N adayın çözünürlüklerini önceden hesapla
        if by_res and vids:
            try:
                import concurrent.futures as _cf
                n = max(1, int(early_subset or 1))
                subset = vids[:n]
                with _cf.ThreadPoolExecutor(max_workers=min(n, len(subset))) as _ex:
                    list(_ex.map(lambda v: getattr(v, 'resolution'), subset))
                # Eğer 1080+ bulunan varsa doğrudan onu al
                cands = [v for v in subset if (v.resolution or default_res) >= 1080 and v.is_working]
                if cands:
                    pick = sorted(cands, key=lambda v: SUPPORTED.index(v.player))[0]
                    callback({"current": len(vids), "total": len(vids), "player": pick.player, "status": "çalışıyor"})
                    return pick
            except Exception:
                pass

        for i,vid in enumerate(vids.copy(),start=1):
            hook_dict = {**hook_dict, "current": i, "player": vid.player}
            callback({**hook_dict, "status": "üstbilgi çekiliyor"})
            if not vid.is_working:
                callback({**hook_dict, "status": "çalışmıyor"})
                vids.remove(vid)
                continue
            # Çözünürlük önemli değilse ya da max çözünürlük bulunduysa videoyu döndür.
            if not by_res or (vid.resolution or default_res) >= 1080:
                callback({**hook_dict, "current":len(vids), "status": "çalışıyor"})
                return vid
        if vids == []:
            callback({**hook_dict, "player": None, "status": "hiçbiri çalışmıyor"})
            return None
        # 1080+ bulunamadıysa, en yüksek çözünürlüğü seç.
        vid = max(vids, key = lambda x:x.resolution or default_res)
        callback({**hook_dict, "player": vid.player , "status": "çalışıyor"})
        return vid


class Video:
    """
    Bir bölüm adına yüklenmiş herhangi bir videoyu temsil eden obje.

    Öznitelikler:
    - path: Video'nun türkanime'deki hash'li dizin yolu.
    - bolum: Video'nun ait olduğu bölüm objesi.
    - fansub: eğer belirtilmişse, videoyu yükleyen fansub'un ismi.
    - url: Videonun decrypted gerçek url'si, örn: https://youtube.com/watch?v=XXXXXXXX
    """
    def __init__(self,bolum,path,player=None,fansub=None,log_handler=LogHandler):
        self.path = path
        self.player = player
        self.fansub = fansub
        self.bolum = bolum
        self._resolution = None
        self._info = None
        self._url = None
        self._is_working = None
        self.is_supported = self.player in SUPPORTED

        self.ydl_opts = {
          'logger': log_handler,
          'quiet': True,
          'ignoreerrors': 'only_download',
          'retries': 5,
          'fragment_retries': 10,
          'restrictfilenames': True,
          'nocheckcertificate': True,
          'concurrent_fragment_downloads': 5,
        }
        if self.player == "ALUCARD(BETA)":
            self.ydl_opts['impersonate'] = ImpersonateTarget("chrome")

    @property
    def url(self):
        if self._url is None:
            if "/" in self.path:
                src = fetch(self.path)
                cipher = re.findall(r"\/embed\/#\/url\/(.*?)\?status",src)[0]
            else: # Zaten seçili video ise
                cipher = self.path
            plaintext = get_real_url(cipher)
            # "\\/\\/fembed.com\\/v\\/0d1e8ilg"  -->  "https://fembed.com/v/0d1e8ilg"
            self._url = "https:"+json.loads(plaintext)
            self._url = self._url.replace("uqload.io","uqload.com") # .com mirror'unu kullan
            if "turkanime" in self._url: # Alucard, Amaterasu, Bankai, HDVID
                self._url = unmask_real_url(self._url)
                self.is_working = False if "turkanime" in self._url else True
        return self._url

    @property
    def info(self):
        if self._info is None:
            assert self.is_supported, "Bu player desteklenmiyor."
            with YoutubeDL(self.ydl_opts) as ydl:
                raw_info = ydl.extract_info(self.url, download=False)
                info = ydl.sanitize_info(raw_info)
            if not info:
                self._info = {}
                return self._info
            # nedense mpv direct=True ise oynatmıyor
            if isinstance(info, dict) and "direct" in info:
                del info["direct"]
            # false-pozitifleri önlemek için.
            if isinstance(info, dict) and info.get("video_ext") == "html":
                info = None
            self._info = info
        return self._info

    @property
    def resolution(self):
        """ Video çözünürlüğünü ara, bulunamadıysa None. """
        if self._resolution is None:
            info = self.info
            if not isinstance(info, dict):
                self._resolution = 0
                return self._resolution
            formats = info.get("formats")
            res = info.get("resolution")
            if res and isinstance(res, str) and re.search(r'\d{2,4}', res):
                res = int(re.findall(r'\d{2,4}', res)[-1])
            elif isinstance(formats, list) and formats:
                first_format = formats[0]
                if isinstance(first_format, dict) and "height" in first_format:
                    best_format = max(formats, key=lambda x: (x.get("height") or 0) if isinstance(x, dict) else 0)
                    res = best_format.get("height") if isinstance(best_format, dict) else None
                elif isinstance(first_format, dict) and "format_id" in first_format:
                    fid = first_format.get("format_id")
                    if isinstance(fid, str):
                        res = {"sd": 480, "hd": 720, "fhd": 1080, "hq": 2160}.get(fid)
                else:
                    # Ek fallback: vcodec isimlerinden veya tbr'den yaklaşık çözünürlük tahmini
                    try:
                        t = max(formats, key=lambda x: ((x.get("height") or 0) if isinstance(x, dict) else 0, (x.get("tbr") or 0) if isinstance(x, dict) else 0))
                        if isinstance(t, dict):
                            res = t.get("height") or (720 if (t.get("tbr") or 0) > 1500 else 480)
                        else:
                            res = None
                    except Exception:
                        res = None
            self._resolution = res or 0
            # Son çare: mpv ile çözünürlük oku
            if not self._resolution:
                try:
                    cmd = [
                        "mpv", "--no-config", "--no-audio", "--no-video",
                        "--frames=1", "--really-quiet",
                        "--term-playing-msg=${video-params/w}x${video-params/h}",
                        self.url,
                    ]
                    _res = sp.run(cmd, text=True, stdout=sp.PIPE, stderr=sp.PIPE, timeout=10)
                    out = (_res.stdout or "") + (_res.stderr or "")
                    mm = re.findall(r"(\d{3,4})x(\d{3,4})", out)
                    if mm:
                        self._resolution = int(mm[-1][1])
                except Exception:
                    pass
        return self._resolution

    @property
    def is_working(self):
        """ Video çalışıyor mu? """
        assert self.is_supported, "Bu player desteklenmiyor."
        if self._is_working is None:
            try:
                if "turkanime" in self.url:
                    raise LookupError
                self._is_working = self.info not in (None, {})
            except:
                self._is_working = False
        return self._is_working

    @is_working.setter
    def is_working(self,value):
        self._is_working = value

    def indir(self, callback=None, output=""):
        """ info.json'u kullanarak videoyu indir """
        assert self.is_working, "Video çalışmıyor."
        seri_slug = self.bolum.anime.slug if self.bolum.anime else ""
        output = join(output, seri_slug, self.bolum.slug)
        opts = self.ydl_opts.copy()
        if callback:
            opts['progress_hooks'] = [callback]
        opts['outtmpl'] = {'default': output + r'.%(ext)s'}
        with NamedTemporaryFile("w",delete=False) as tmp:
            json.dump(self.info, tmp)
        with YoutubeDL(opts) as ydl:
            ydl.download_with_info_file(tmp.name)
        remove(tmp.name)

    def oynat(self, dakika_hatirla=False ,izlerken_kaydet=False, mpv_opts=[]):
        """ Oynatmak için yt-dlp + mpv kullanıyoruz. """
        assert self.is_working, "Video çalışmıyor."
        
        # Platform ve mimari bilgisini al
        platform_info = get_platform()
        arch = get_arch()
        
        # ARM mimarileri için Android MPV kullan
        if arch in ["armv7l", "arm64"] or "aarch64" in platform_info:
            # Android MPV komutu
            cmd = [
                "nohup", "am", "start", "--user", "0", 
                "-a", "android.intent.action.VIEW",
                "-d", self.url,
                "-n", "is.xyz.mpv/.MPVActivity"
            ]
            # Android için stdout/stderr'ı /dev/null'a yönlendir
            return sp.run(cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        
        # Standart masaüstü MPV komutu
        with NamedTemporaryFile("w",delete=False) as tmp:
            json.dump(self.info, tmp)
        cmd = [
            "mpv",
            "--no-input-terminal",
            "--msg-level=all=error",
            "--script-opts=ytdl_hook-ytdl_path=yt-dlp,ytdl_hook-try_ytdl_first=yes",
            "--ytdl-raw-options=load-info-json=" + tmp.name,
            "ytdl://" + self.bolum.slug # Kaldığın yerden devam etmenin çalışması için.
        ]

        if self.player == "ALUCARD(BETA)":
            cmd += ["--demuxer-lavf-o=protocol_whitelist=[file,tcp,tls,https],http_keep_alive=0,http_persistent=0"]
            cmd += ["--cache=yes", get_alucard_m3u8(self.url) ]
            del cmd[4]

        if dakika_hatirla:
            mpv_opts.append("--save-position-on-quit")
        if izlerken_kaydet:
            mpv_opts.append("--stream-record")
        for opt in mpv_opts:
            cmd.insert(1,opt)
        return sp.run(cmd, text=True, stdout=sp.PIPE, stderr=sp.PIPE)

    def get(self, key, default=None):
        """Dictionary-like get method for compatibility."""
        if key == 'url':
            return self.url
        elif key == 'label':
            return getattr(self, 'fansub', None) or self.player
        elif key == 'player':
            return self.player
        return default
