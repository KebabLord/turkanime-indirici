"""
gereksinim_kontrol(progress=None)
  - exe gereksinimlerin kurulu olup olmadığını kontrol et, tercihe bağlı kur.

webdriver_hazirla(progress=None) : driver
  - seleniumu hazırlar, sorunları giderir ve driver objesini döndürür.
"""

from sys import exit as kapat
import subprocess as sp
from os import name,system
from time import sleep
from prompt_toolkit import styles
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import SessionNotCreatedException
from questionary import confirm

from .dosyalar import DosyaManager,DownloadGereksinimler

def clear():
    """ Daha kompakt görüntü için her prompt sonrası clear
        Debug yapacaksanız devre dışı bırakmanız önerilir.
    """
    system('cls' if name == 'nt' else 'clear')

def gereksinim_kontrol(progress=None):
    """ Gereksinimlerin erişilebilir olup olmadığını kontrol eder """
    stdout, bulunmayan = "\n", []
    for gereksinim in ["geckodriver","youtube-dl","mpv"]:
        status = sp.Popen(f'{gereksinim} --version',stdout=sp.PIPE,stderr=sp.PIPE,shell=True).wait()
        if status==1 or status==127:
            stdout += f"x {gereksinim} bulunamadı.\n"
            bulunmayan.append(gereksinim)
        elif status==0:
            stdout += f"+ {gereksinim} bulundu.\n"
        else:
            stdout += f"x {gereksinim} bulundu ancak çalıştırılamadı.\n"
            if name=="nt" and gereksinim=="youtube-dl":
                # youtube-dl muhtemelen msvcr100.dll eksik hatası verdi
                # https://github.com/ytdl-org/youtube-dl/issues/10278#issuecomment-238692956
                bulunmayan.append("vcredist_x86")
                stdout += "  - msvcr100.dll hatasıyla karşılaştıysanız vcredist_x86 kurulacak.\n"

    if not bulunmayan:
        if progress and not progress.tasks[0].visible:
            progress.start()
        return
    if progress:
        progress.stop()
    print(stdout+"\nBelirtilen program yada programlar",
        "program dizininde yada sistem PATH'ında bulunamadı.")
    if name=="nt" and confirm("Otomatik kurulsun mu?").ask():
        DownloadGereksinimler(bulunmayan)
        system('cls' if name == 'nt' else 'clear')
        gereksinim_kontrol(progress)
        return
    print("Gereksinimleri manuel olarak kurmak için lütfen klavuzdaki talimatları izleyin.",end="")
    sleep(3)
    print()
    kapat(1)


def webdriver_hazirla(progress=None):
    """ Selenium webdriver'ı hazırla """
    dosya = DosyaManager()
    options = Options()
    options.add_argument('--headless')
    if dosya.ayar.has_option("TurkAnime","firefox konumu"):
        options.binary_location = dosya.ayar.get("TurkAnime","firefox konumu")
    profile = webdriver.FirefoxProfile()
    profile.set_preference("dom.webdriver.enabled", False)
    profile.set_preference('useAutomationExtension', False)
    profile.set_preference('permissions.default.image', 2)
    profile.set_preference("network.proxy.type", 0)
    profile.update_preferences()
    desired = webdriver.DesiredCapabilities.FIREFOX
    if name == 'nt':
        try:
            return webdriver.Firefox(
                profile, options=options,service_log_path='NUL',
                executable_path=r'geckodriver.exe', desired_capabilities=desired
            )
        except SessionNotCreatedException:
            if progress:
                progress.stop()
            input("Yazılım firefox'un kurulu olduğu dizini tespit edemedi\n"+
                "Manual olarak Program Files'ten firefox.exe'yi"+
                "seçmek için yönlendirileceksiniz.\n\n( Devam etmek için entera basın )")
            from easygui import fileopenbox
            firefox_dizin=fileopenbox("/")
            if firefox_dizin:
                dosya.ayar.set("TurkAnime","firefox konumu",firefox_dizin)
                dosya.save_ayarlar()
                input("Programı yeniden başlatmalısınız. \n\n( Devam etmek için entera basın )")
            kapat()
    return webdriver.Firefox(
        profile, options=options,
        service_log_path='/dev/null',desired_capabilities=desired
        )

prompt_tema = styles.Style([
    ('qmark', 'fg:#5F819D bold'),
    ('question', 'fg:#289c64 bold'),
    ('answer', 'fg:#48b5b5 bg:#hidden bold'),
    ('pointer', 'fg:#48b5b5 bold'),
    ('highlighted', 'fg:#07d1e8'),
    ('selected', 'fg:#48b5b5 bg:black bold'),
    ('separator', 'fg:#6C6C6C'),
    ('instruction', 'fg:#77a371'),
    ('text', ''),
    ('disabled', 'fg:#858585 italic')
])
