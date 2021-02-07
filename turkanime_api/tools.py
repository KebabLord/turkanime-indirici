from sys import exit as kapat
import subprocess as sp
from os import name
from prompt_toolkit import styles
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

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
        print(stdout+"\nBelirtilen program yada programlar",
            "program dizininde yada sistem PATH'ında bulunamadı.",
            "Lütfen klavuzdaki kurulum talimatlarını uygulayın.")
        kapat(1)

def webdriver_hazirla():
    """ Selenium webdriver'ı hazırla """
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
