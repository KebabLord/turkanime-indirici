from sys import exit as kapat
import subprocess as sp
from os import name
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from .anime import AnimeSorgula,Anime
from .players import elementi_bekle

def gereksinim_kontrol():
    """ Gereksinimlerin erişilebilir olup olmadığını kontrol eder """
    eksik=False
    stdout="\n"
    for gereksinim in ["geckodriver","youtube-dl","mpv"]:
        status = sp.Popen(f'{gereksinim} --version',stdout=sp.PIPE,stderr=sp.PIPE,shell=True).wait()
        if status>0:
            stdout += f"x {gereksinim} bulunamadı.\n"
            eksik=True
        else:
            stdout += f"+ {gereksinim} bulundu.\n"
    if eksik:
        print(stdout+"\nBelirtilen program yada programlar, program dizininde yada sistem PATH'ında bulunamadı. Lütfen klavuzdaki kurulum talimatlarını uygulayın.")
        kapat(1)

def webdriver_hazirla():
    """ Selenium webdriver'ı hazırla """
    print(" "*50+"\rSürücü başlatılıyor...",end="\r")

    options = Options()
    options.add_argument('--headless')
    profile = webdriver.FirefoxProfile()
    profile.set_preference("dom.webdriver.enabled", False)
    profile.set_preference('useAutomationExtension', False)
    profile.set_preference('permissions.default.image', 2)
    profile.set_preference("network.proxy.type", 0)
    profile.update_preferences()
    desired = webdriver.DesiredCapabilities.FIREFOX
    if name == 'nt':
        return webdriver.Firefox(
            profile, options=options,service_log_path='NUL',
            executable_path=r'geckodriver.exe', desired_capabilities=desired
        )

    return webdriver.Firefox(
        profile, options=options,
        service_log_path='/dev/null',desired_capabilities=desired
    )
