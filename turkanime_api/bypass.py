"""
BYPASS Modülü, TürkAnime'deki şifreyle saklanan elementlerini çözmek
ve firewall'i kandirmak için gerekli fonksiyonlari / rutinleri içerir.

- Fetch(url)->str                   Firefox TLS & HTTP/3 taklitli GET Request fonksiyonu

- obtain_key()->bytes               TürkAnime'nin iframe şifrelerken kullandigi AES anahtari bulur
- decrypt_cipher(key, data)->str    CryptoJS.AES.decrypt python implementasyonu
- get_real_url(cipher)->str         TürkAnime'nin iframe şifresini çözüp gerçek video URL'sini getir

- decrypt_jsjiamiv7(cipher, key):   Reverse jsjiamiv7 -> decodeURIComponent(base64(RC4(KSA + PRGA)))
- obtain_csrf()->str                TürkAnime'nin encrypted tuttuğu csrf tokeni bul, decryptle,getir
- unmask_real_url(masked_url):      Alucard, Bankai, Amaterasu, HDVID url maskesini çöz.
"""
import os
import re
from base64 import b64decode
import json
from hashlib import md5
from appdirs import user_cache_dir
from Crypto.Cipher import AES

from curl_cffi import requests
session = None
BASE_URL = "https://turkanime.co/"


def fetch(path, headers={}):
    """Curl-cffi kullanarak HTTP/3 ve Firefox TLS Fingerprint Impersonation
       eyleyerek GET request atmak IUAM aktif olmadigi sürece CF'yi bypassliyor. """
    global session, BASE_URL
    # Init: Çerezleri cart curt oluştur, yeni domain geldiyse yönlendir.
    if session is None:
        session = requests.Session(impersonate="firefox", allow_redirects=True)
        res = session.get(BASE_URL)
        assert res.status_code == 200, ConnectionError
        BASE_URL = res.url
        BASE_URL = BASE_URL[:-1] if BASE_URL.endswith('/') else BASE_URL
    if path is None:
        return ""
    # Get request'i yolla
    path = path if path.startswith("/") else "/" + path
    headers["X-Requested-With"] = "XMLHttpRequest"
    return session.get(BASE_URL + path, headers=headers).text


"""
Videoların gerçek URL'lerini decryptleyen fonksiyonlar
örn: eyJjdCI6IldXUmRNWFdCMG15T253dXUmRNWFd3V -> https://dv97.sibnet.ru/15/80/112314.mp4
"""

def obtain_key() -> bytes:
    """
    Şifreli iframe url'sini decryptlemek için gerekli anahtarı döndürür. 
    Javascript dosyalarının isimleri ve anahtar, periyodik olarak değiştiğinden,
    güncel şifre için aşağıdaki algoritmayla tersine mühendislik yapıyoruz:

    - /embed/ endpointin çağırdığı 2. javascript dosyasını aç.
    - Bu dosyanın içinde çağırılan diğer iki javascript dosyasını da regexle bul.
    - Bu iki dosyadan içinde "decrypt" ifadesi geçeni seç
    - Bir liste olarak obfuscate edilmiş bu javascript dosyasından şifreyi edin.
    """

    try:
        # İlk javascript dosyasını ve importladığı dosyaları bul.
        js1 = fetch(
                re.findall(
                    r"/embed/js/embeds\..*?\.js",
                    fetch("/embed/#/url/"))[1]
            )
        js1_imports = re.findall("[a-z0-9]{16}",js1)
        # Bu dosyalardan içinde "decrypt" ifadesi geçen dosyayı bul.
        j2 = fetch(f'/embed/js/embeds.{js1_imports[0]}.js')
        if "'decrypt'" not in j2:
            j2 = fetch(f'/embed/js/embeds.{js1_imports[1]}.js')
        # Obfuscated listeyi parse'la.
        obfuscate_list = re.search(
                'function a\\d_0x[\\w]{1,4}\\(\\){var _0x\\w{3,8}=\\[(.*?)\\];',j2
            ).group(1)
        # Listedeki en uzun elemanı, yani şifremizi bul.
        return max(
            obfuscate_list.split("','"),
            key=lambda i:len( re.sub(r"\\x\d\d","?",i))
        ).encode()
    except IndexError:
        return False



def decrypt_cipher(key: bytes, data: bytes) -> str:
    """ CryptoJS.AES.decrypt'in python implementasyonu
        referans:
            - https://stackoverflow.com/a/36780727
            - https://gist.github.com/ysfchn/e96304fb41375bad0fdf9a5e837da631
    """
    def salted_key(data: bytes, salt: bytes, output: int = 48):
        assert len(salt) == 8, len(salt)
        data += salt
        key = md5(data).digest()
        final_key = key
        while len(final_key) < output:
            key = md5(key + data).digest()
            final_key += key
        return final_key[:output]
    def unpad(data: bytes) -> bytes:
        return data[:-(data[-1] if isinstance(data[-1],int) else ord(data[-1]))]
    # Remove URL path from the string.
    b64 = b64decode(data)
    cipher = json.loads(b64)
    cipher_text = b64decode(cipher["ct"])
    iv = bytes.fromhex(cipher["iv"])
    salt = bytes.fromhex(cipher["s"])
    # Create new AES object with using salted key as key.
    crypt = AES.new(salted_key(key, salt, output=32), iv=iv, mode=AES.MODE_CBC)
    # Decrypt link and unpad it.
    try:
        return unpad(crypt.decrypt(cipher_text)).decode("utf-8")
    except UnicodeDecodeError:
        return False



def get_real_url(url_cipher: str, cache=True) -> str:
    """ Videonun gerçek url'sini decrypt'le, parolayı da cache'le. """
    cache_file = os.path.join(user_cache_dir(),"turkanimu_key.cache")
    url_cipher = url_cipher.encode()

    # Daha önceden cache'lenmiş key varsa onunla şifreyi çözmeyi dene.
    if cache and os.path.isfile(cache_file):
        with open(cache_file,"r",encoding="utf-8") as f:
            cached_key = f.read().strip().encode()
            plaintext = decrypt_cipher(cached_key,url_cipher)
        if plaintext:
            return plaintext

    # Cache'lenmiş key işe yaramadıysa, yeni key'i edin ve decryptlemeyi dene.
    key = obtain_key()
    plaintext = decrypt_cipher(key,url_cipher)
    if not plaintext:
        raise ValueError("Embed URLsinin şifresi çözülemedi.")
    # Cache'i güncelle
    if cache:
        with open(cache_file,"w",encoding="utf-8") as f:
            f.write(key.decode("utf-8"))
    return plaintext




"""
TürkAnime'nin kendi player'larından url çıkartan fonksiyonlar (Alucard, Bankai, Amaterasu vs.)
örn: http://turkanime.co/sources/UW1EN2VPcExLUXpiaDRqcnV0d -> https://alucard.stream/cdn/playlist/3S3CtAJxAZ
"""

PLAYERJS_URL = "/js/player.js"
PLAYERJS_CSRF = None

def decrypt_jsjiamiv7(ciphertext, key):
    """
    jsjiamiv7 obfuscator ile şifrelenmiş bi cipher'ı decryptleyen fonksiyon
    - Cipher nedense non-standart bir alfabeyle translate edilmiş, onu normal base64 alfabesine çevir
    - Sonra base64 decode eyle
    - Sonra RC4 (KSA + PRGA) algoritması ile şifreyi çöz https://en.wikipedia.org/wiki/RC4
    - Galiba bu internette ilk. v5, v6 decode'layan buldum da, v7 decodelayan proje bulamadım.
    """
    _CUSTOM = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/"
    _STD    = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    _TRANSLATE = str.maketrans(_CUSTOM, _STD)
    t = ciphertext.translate(_TRANSLATE)
    t += "=" * (-len(t) % 4)
    data = b64decode(t).decode("utf-8")

    S = list(range(256))
    j = 0
    klen = len(key)
    # KSA
    for i in range(256):
        j = (j + S[i] + ord(key[i % klen])) & 0xff
        S[i], S[j] = S[j], S[i]
    # PRGA
    i = j = 0
    out = []
    for ch in data:
        i = (i + 1) & 0xff
        j = (j + S[i]) & 0xff
        S[i], S[j] = S[j], S[i]
        out.append(chr(ord(ch) ^ S[(S[i] + S[j]) & 0xff]))
    return "".join(out)


def obtain_csrf():
    """
    /js/player.js dosyasındaki jsjiamiv7 ile şifrelenmiş csrf tokeni edin.
    - regex ile key'i çıkar ve ciphertext olabilecek bütün text'leri çıkar
    - bütün adayları key ile decryptlemeyi dene, başarılı çıkan sonuç csrf tokenidir.
    """
    res = fetch(PLAYERJS_URL)
    # Key'i çıkar
    key = re.findall(r"csrf-token':[^\n\)]+'([^']+)'\)", res, re.IGNORECASE)
    # Bütün Ciphertext adaylarını çıkar
    candidates = re.findall(r"'([a-zA-Z\d\+\/]{96,156})',",res)
    assert key and candidates
    key = key[0]

    # Hepsini decrypt'lemeyi dene, başarılı olanı döndür
    decrypted_list = [decrypt_jsjiamiv7(ct,key) for ct in candidates]
    return next((i for i in decrypted_list if re.search("^[a-zA-Z/\+]+$",i)), None)


def unmask_real_url(url_mask):
    """ TürkAnime'nin kendi playerlarının url maskesini çözer. """
    global PLAYERJS_CSRF
    assert "turkanime" in url_mask
    if PLAYERJS_CSRF is None:
        try:
            PLAYERJS_CSRF = obtain_csrf()
            if PLAYERJS_CSRF is None:
                raise LookupError
        except:
            print("ERROR: CSRF bulunamadı.")
            return url_mask

    MASK = url_mask.split("/player/")[1]
    headers = {"Csrf-Token": PLAYERJS_CSRF, "cf_clearance": "dull"}
    res = fetch(f"/sources/{MASK}/false",headers)

    try:
        url = json.loads(res)["response"]["sources"][-1]["file"]
        if url.startswith("//"):
            url = "https:" + url
    except:
        return url_mask
    return url
