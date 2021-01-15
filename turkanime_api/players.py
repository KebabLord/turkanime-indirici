import re
from sys import exit as kapat
import subprocess as sp
from bs4 import BeautifulSoup as bs4

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

def check_video(url):
    """ Video yaşıyor mu kontrol eder """
    print("\033[2K\033[1GVideo yaşıyor mu kontrol ediliyor..",end="\r")
    test = sp.Popen(f"youtube-dl --no-warnings -F '{url}'",stdout=sp.PIPE,shell=True)
    stdout = test.communicate()[0].decode()
    stdexit   = test.returncode
    if stdexit == 0 and "php" not in stdout:
        print("\033[2K\033[1GVideo aktif, başlatılıyor..",end="\r")
        return True
    print("\033[2K\033[1GPlayerdaki video silinmiş, sıradakine geçiliyor",end="\r")
    return False

def url_getir(driver):
    """ Ajax sorgularıyla tüm player url'lerini (title,url) formatında listeler
        Ardından desteklenen_player'da belirtilen hiyerarşiye göre sırayla desteklenen
        ve çalışan bir alternatif bulana dek bu listedeki playerları itere eder.

        Prosedür:
            - Herhangi bir fansub butonundan bölümün hash kodunu çek
            - Bölüm hash'ini kullanarak tüm playerları getir
            - Her bir player'ın iframe sayfasındaki gerçek url'yi decryptleyip test et
    """
    print("\033[2K\033[1GVideo url'si çözülüyor..",end="\r")
    try:
        bolum_hash = re.findall(
                r"rik\('(.*)&f",
                driver.find_element_by_css_selector("button.btn.btn-sm").get_attribute("onclick")
            )[0]
    except TypeError: # Yalnızca bir fansub olduğunda hash'i playerlardan al
        bolum_hash = re.findall(
                r"rik\('(.*)&f",
                driver.find_elements_by_css_selector("button.btn.btn-sm")[2].get_attribute("onclick")
            )[0]

    soup = bs4(
        driver.execute_script(f"return $.get('ajax/videosec&b={bolum_hash}')"),
        "html.parser"
        )

    parent = soup.find("div", {"id": "videodetay"}).findAll("div",class_="btn-group")[1]
    videos = [ (i.text, i.get("onclick").split("'")[1]) for i in parent.findAll("button") if "btn-danger" not in str(i) ]

    for player in desteklenen_players:
        for uri in [ u for t,u in videos if player in t ]:
            try:
                iframe_src = driver.execute_script("return $.get('{}')".format(
                        re.findall(
                            r"(\/\/www.turkanime.net\/iframe\/.*)\" width",
                            driver.execute_script(f"return $.get('{uri}')")
                        )[0]
                    ))
            except IndexError:
                continue
            else:
                if "Sayfayı yenileyip tekrar deneyiniz..." in iframe_src:
                    print("Site Bakımda.")
                    kapat()

            var_iframe = re.findall(r'{"ct".*?}',iframe_src)[0]
            var_sifre = re.findall(r"pass.*?\'(.*)?\'",iframe_src)[0]

            # Türkanimenin iframe şifreleme algoritması.
            url = "https:"+driver.execute_script(f"var iframe='{var_iframe}';var pass='{var_sifre}';"+r"""
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
            return JSON.parse(CryptoJS.AES.decrypt(iframe, pass, {format: CryptoJSAesJson}).toString(CryptoJS.enc.Utf8));
            """)

            if check_video(url):
                return url
