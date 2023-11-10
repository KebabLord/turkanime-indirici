"""
create_webdriver() -> driver
  - seleniumu hazırlar ve driver objesini döndürür.

find_firefox_executable() -> path:str
  - bilinen dizinlerde firefox binary'sini arar
"""

from os import name,path,getlogin
from time import time
from distutils import spawn
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import SessionNotCreatedException

# Gerekli çerez & dosyaların yüklendiği dull sayfa
init_url = "https://turkanime.co/kullanici/anonim"

def find_firefox_executable():
    """ firefox.exe'yi bilinen konumlarda ara. """
    possible_locations = [
        "C:\\Program Files\\Mozilla Firefox\\firefox.exe",
        "C:\\Program Files (x86)\\Mozilla Firefox\\firefox.exe",
        "C:\\Program Files\\Firefox Developer Edition\\firefox.exe",
        f"C:\\Users\\{getlogin()}\\AppData\\Local\\Mozilla Firefox\\firefox.exe"
        "/Applications/Firefox.app/Contents/MacOS/firefox",
        "/usr/bin/firefox",
        "/usr/local/bin/firefox",
        "/usr/bin/firefox-esr",
        "/usr/local/bin/firefox-esr",
    ]
    for location in possible_locations:
        if path.exists(location):
            return location
    raise SessionNotCreatedException("firefox'un konumu bulunamadı.")


def create_webdriver(profile=None,headless=True,firefox_path=None,preload_ta=True):
    """ Selenium webdriver'ı hazırla. """
    options = Options()
    if headless:
        options.add_argument('--headless')
    if firefox_path:
        options.binary_location = firefox_path
    elif not spawn.find_executable("firefox"):
        firefox_path = find_firefox_executable()
    if not profile:
        profile = webdriver.FirefoxProfile()
        profile.set_preference("dom.webdriver.enabled", False)
        profile.set_preference('useAutomationExtension', False)
        profile.set_preference('permissions.default.image', 2)
        profile.set_preference("network.proxy.type", 0)
        profile.update_preferences()
    desired = webdriver.DesiredCapabilities.FIREFOX
    if name == 'nt':
        driver = webdriver.Firefox(
            profile, options=options,service_log_path='NUL',
            executable_path=r'geckodriver.exe', desired_capabilities=desired
        )
    else:
        driver = webdriver.Firefox(
            profile, options=options,
            service_log_path='/dev/null',desired_capabilities=desired
            )
    if preload_ta:
        driver.get(init_url)
    return driver


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
