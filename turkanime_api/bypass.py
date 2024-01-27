import os
import re
from base64 import b64decode
import json
from hashlib import md5
from appdirs import user_cache_dir
from Crypto.Cipher import AES


def obtain_key(driver) -> bytes:
    """
    Şifreli iframe url'sini decryptlemek için gerekli anahtarı döndürür. 
    Javascript dosyalarının isimleri ve anahtar, periyodik olarak değiştiğinden,
    güncel şifre için aşağıdaki algoritmayla tersine mühendislik yapıyoruz:

    - /embed/ endpointin çağırdığı 2. javascript dosyasını aç.
    - Bu dosyanın içinde çağırılan diğer iki javascript dosyasını da regexle bul.
    - Bu iki dosyadan içinde "decrypt" ifadesi geçeni seç
    - Bir liste olarak obfuscate edilmiş bu javascript dosyasından şifreyi edin.
    """
    def fetch(path):
        return driver.execute_script(f"return $.get('{path}')")
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



def get_real_url(driver, url_cipher: str, cache=True) -> str:
    """ obtain_key & decrypt_cipher fonksiyonlarını kombine eden parolayı cache'leyen fonksiyon. """
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
    key = obtain_key(driver)
    plaintext = decrypt_cipher(key,url_cipher)
    if not plaintext:
        raise ValueError("Embed URLsinin şifresi çözülemedi.")
    # Cache'i güncelle
    if cache:
        with open(cache_file,"w",encoding="utf-8") as f:
            f.write(key.decode("utf-8"))
    return plaintext
