import re
import subprocess as sp
from time import time
import base64
from selenium.common.exceptions import NoSuchElementException,JavascriptException
from rich.progress import Progress, BarColumn, SpinnerColumn
from rich import print as rprint
from questionary import select
from bs4 import BeautifulSoup as bs4
from .tools import prompt_tema
from .dosyalar import DosyaManager

desteklenen_players = [
    "SIBNET",
    "MAIL",
    "MYVI",
    "VK",
    "GPLUS",
    "GDRIVE",
    "YADISK",
    "VIDMOLY",
    "YOURUPLOAD",
    "DAILYMOTION",
    "SENDVID",
    "ODNOKLASSNIKI"
]

def elementi_bekle(selector,_driver):
    """ Element yüklenene dek bekler. Eğer 10 saniye
        boyunca yanıt alamazsa error verir.
    """
    start=round(time())
    while round(time())-start<10:
        try:
            _driver.find_element_by_css_selector(selector)
        except NoSuchElementException:
            continue
        break
    else:
        raise ConnectionError("TürkAnime'ye ulaşılamıyor")

def check_video(url):
    """ Video yaşıyor mu kontrol eder """
    if "_myvideo" in url:
        return False
    test = sp.Popen(f'youtube-dl --no-warnings -F "{url}"',stdout=sp.PIPE,shell=True)
    stdout = test.communicate()[0].decode()
    stdexit   = test.returncode
    if stdexit == 0 and "php" not in stdout:
        return True
    return False

def fansub_sec(src):
    """ Fansubları parselar, hash kodunu çeker ve kullanıcıdan seçim yapmasını ister """
    fansub_bar = re.search(".*birden fazla grup",src)
    if not fansub_bar:
        return ""
    fansublar = re.findall("(&f=.*?)\'.*?</span> (.*?)</a>",fansub_bar.group())

    secilen_sub = select(
        "Fansub seçiniz",
        [{"name":i[1],"value":i[0]} for i in fansublar],
        style=prompt_tema,
        instruction=" "
    ).ask()
    return secilen_sub if secilen_sub else ""

def decrypt_cipher(driver,cipher,password):
    """Prosedür:
        - Talep edilen bölümün hash kodunu çek
        - Bölüm hash'ini kullanarak tüm playerları getir
        - Her bir player'ın embed sayfasındaki gerçek url'yi decryptle
    """
    try:
        return "https:"+driver.execute_script(r"""
            var CryptoJSAesJson = {
                stringify: function (cipherParams) {
                    var j = {ct: cipherParams.ciphertext.toString(CryptoJS.enc.Base64)};
                    if (cipherParams.iv) j.iv = cipherParams.iv.toString();
                    if (cipherParams.salt) j.s = cipherParams.salt.toString();
                    return JSON.stringify(j).replace(/\s/g, '');
                },
                parse: function (jsonStr) {
                    console.log(jsonStr);
                    var j = JSON.parse(jsonStr);
                    var cipherParams = CryptoJS.lib.CipherParams.create({ciphertext: CryptoJS.enc.Base64.parse(j.ct)});
                    if (j.iv) cipherParams.iv = CryptoJS.enc.Hex.parse(j.iv);
                    if (j.s) cipherParams.salt = CryptoJS.enc.Hex.parse(j.s);
                    return cipherParams;
                }
            };
            return JSON.parse(CryptoJS.AES.decrypt('%s', '%s', {format: CryptoJSAesJson}).toString(CryptoJS.enc.Utf8));
            """ % (cipher,password))
    except JavascriptException:
        return False

def refresh_key(driver):
    """
    - Embed endpoint'inin header'ındaki 2. javascripti parse et
    - Bu javascript içinde regexle importlanan 2 javascripti de bul
    - JS dosyalarının aralarından 'decrypt' ifadesi geçeni seç
    - obfuscate listdeki en uzun item bizim keyimiz
    """
    try:
        fetch = lambda x: driver.execute_script(f"return $.get('{x}')")
        js1 = fetch(
                re.findall(
                    "/embed/js/embeds\..*?\.js",
                    fetch("/embed/#/url/"))[1]
            )

        js1_imports = re.findall("[a-z0-9]{16}",js1)

        j2 = fetch(f'/embed/js/embeds.{js1_imports[0]}.js')
        if "'decrypt'" not in j2:
            j2 = fetch(f'/embed/js/embeds.{js1_imports[1]}.js')

        obfuscate_list = re.search(
                'function a\\d_0x[\\w]{1,4}\\(\\){var _0x\\w{3,8}=\\[(.*?)\\];',j2
            ).group(1)

        return max( # Bu listedeki en uzun eleman aradığımız şifre.
            obfuscate_list.split("','"),
            key=lambda i:len( re.sub(r"\\x\d\d","?",i))
        )
    except IndexError:
        return False

def url_getir(bolum,driver,manualsub=False):
    """ Ajax sorgularıyla tüm player url'lerini (title,url) formatında listeler
        Ardından desteklenen_player'da belirtilen hiyerarşiye göre sırayla desteklenen
        ve çalışan bir alternatif bulana dek bu listedeki playerları itere eder.
    """
    dosya, url = DosyaManager(), False
    key = base64.b64decode(
            dosya.ayar.get("TurkAnime","key")
        ).decode() if dosya.ayar.has_option("TurkAnime","key") else False

    with Progress(
        SpinnerColumn(),'[progress.description]{task.description}',
        BarColumn(bar_width=40),transient=True) as progress:
        task = progress.add_task("[cyan]Bölüm sayfası getiriliyor..", start=False)
        bolum_src = driver.execute_script(f'return $.get("/video/{bolum}")')

    fansub_hash = fansub_sec(bolum_src) if manualsub else ""
    with Progress(
            SpinnerColumn(),
            '[progress.description]{task.description}',
            BarColumn(bar_width=40)
        ) as progress:
        task = progress.add_task("[cyan]Video url'si çözülüyor..", start=False)

        videos = []
        regex = re.search("videosec&b=(.*?)&", bolum_src)

        if regex:
            bolum_hash = regex.group()
            soup = bs4(
                driver.execute_script(f"return $.get('ajax/videosec&b={bolum_hash}{fansub_hash}')"),
                "html.parser"
                )
            parent = soup.find("div", {"id": "videodetay"}).findAll("div",class_="btn-group")[1]

            for i in parent.findAll("button"):
                if "btn-danger" not in str(i):
                    #              (PLAYER, URI)
                    videos.append( (i.text, i.get("onclick").split("'")[1]) )

        # Tek fansub varsa otomatik yüklenen videoyu da listeye ekle
        for i in re.findall('iframe src=\\"(.*?)\\\".*?span> (.*?)</button>',bolum_src):
            videos.append(i[::-1])

        for player in desteklenen_players:
            for uri in [ u for t,u in videos if player in t ]:
                progress.update(task, description=f"[cyan]{player.title()} url'si getiriliyor..")
                try:
                    cipher = base64.b64decode(re.search(
                        r"\/embed\/#\/url\/(.*?)\?status",
                        driver.execute_script(f"return $.get('{uri}')")
                    )[1]).decode()
                except IndexError:
                    continue

                if key:
                    url = decrypt_cipher(driver,cipher,key)
                elif not url:
                    key = refresh_key(driver)
                    url = decrypt_cipher(driver,cipher,key)
                    dosya.ayar.set(
                        'TurkAnime','key',
                        base64.b64encode(bytes(key,"utf_8")).decode()
                    )
                    dosya.save_ayarlar()
                if not key or not url:
                    continue

                progress.update(task, description="[cyan]Video yaşıyor mu kontrol ediliyor..")
                if check_video(url):
                    progress.update(task,visible=False)
                    rprint("[green]Video aktif, başlatılıyor![/green]")
                    return url
        progress.update(task,visible=False)
        return False
