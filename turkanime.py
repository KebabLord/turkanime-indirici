# Türkanime Video Player/Downloader 2.5.0

# GEREKSİNİMLER - geckodriver, python-selenium, mpv, youtube-dl 

# YAPILACAKLAR LİSTESİ    
"""
- Openload alternatifi eklenicek
- Arama ve bölüm listesi sistemi entegre edilecek
"""
import multiprocessing 
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from time import sleep as delay
from os import system,getpid,name


options = Options()
options.add_argument('--headless')

if name=="nt":
    driver = webdriver.Firefox(options=options,executable_path=r'geckodriver.exe')
    #driver = webdriver.PhantomJS('phantomjs.exe')
    ytdl_prefix=""
    mpv_prefix=""
else:
    driver = webdriver.Firefox(options=options)
    ytdl_prefix=""
    mpv_prefix=""

global hedef

HARICILER = [
        "UMPLOMP"
        "HDVID",
        "SENDVID",
        "STREAMANGO",
]

# Popup kapatıcı
def killPopup():
    if (len(driver.window_handles)>1):
        driver.switch_to.window(driver.window_handles[1])
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        return True
    else:
        return False

def oynat_indir(url_):
    driver.close()
    if (input("indir? (Y/N): ")=="y"):
        filename = hedef[hedef.index("video/")+6:].replace("-","_").replace("/","")+".mp4 "
        basariStatus = system(ytdl_prefix+"youtube-dl -o "+filename+url_+" > ./log")
    else:
        basariStatus = system(mpv_prefix+"mpv "+url_+" > ./log")
    exit()

def checkVideo(url_):
    i = system('youtube-dl -F "'+url_+'"')
    if not(i):
        return True
    else:
        raise


# Fansub listeleyici
fansublar = []
def updateFansublar(n):
    global fansublar
    fansublar = driver.find_elements_by_xpath("//div[@class='panel-body']/div/button")
    if n:
        print("\nMEVCUT FANSUBLAR:")
        for fansub in fansublar:
            print("  >"+fansub.text)
    killPopup()

# Video player listeleyici (fansub seçildikten sonra)
alternatifler = sites = []
def updateAlternatifler(n):
    killPopup()
    global alternatifler,sites
    delay(1.5)
    if n:print("\n\nMEVCUT KAYNAKLAR:")
    alternatifler = driver.find_elements_by_xpath("//div[@class='panel-body']/div[@class='btn-group']/button")
    """while True:
        alternatifler = driver.find_elements_by_xpath("//div[@class='panel-body']/div[@class='btn-group']/button")
        if alternatifler:
            break
        delay(1)
        print("retry")"""
    sites.clear()
    #! "alternatifler" listesinde butonların html kodları ; "sites" listesinde butonların isimleri var
    for alternatif in alternatifler:
        sites.append(alternatif.text)
        if n:print("  >"+alternatif.text)
    killPopup()

def bekleSayfaninYuklenmesini():
    while True:
        try:
            assert "Bölüm" in driver.title
        except:
            continue
        finally:
            break


# HARİCİ ALTERNATİFLER 
# Türkanimenin yeni sekmeye attığı harici playerlar: hdvid,rapidvideo,streamango,userscloud,sendvid
def getExternalVidOf(NYAN):
    try:
        updateAlternatifler(0)
        print("\n\n"+NYAN+" alternatifine göz atılıyor")
        alternatifler[sites.index(NYAN)].click() #alternatife tıkla
        delay(5)
        """while True:
            if driver.find_elements_by_css_selector(".video-icerik iframe"):
                break
            delay(1)"""
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe") #iframe'in içine gir
        driver.switch_to.frame(iframe_1)
        url = driver.find_element_by_css_selector("#link").get_attribute("href") #linki ceple
        checkVideo(url)
    except:
            print("Videoya erişilemiyor")
            return False
    else:
        oynat_indir(url)
    finally:
    	driver.switch_to.default_content()


# TÜRKANİME PLAYER
def getTurkanimeVid():
    try: # iki iframe katmanından oluşuyor
        updateAlternatifler(0)
        print("\n\nTürkanime alternatifine göz atılıyor")
        alternatifler[sites.index("TÜRKANİME")].click()
        delay(4)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        iframe_2 = driver.find_element_by_css_selector("iframe")
        driver.switch_to.frame(iframe_2)
        url = driver.find_element_by_css_selector(".jw-media").get_attribute("src")
        checkVideo(url)
    except:
        print("Videoya erişilemiyor")
        return False
    else:
        oynat_indir(url)
    finally:
    	driver.switch_to.default_content()

# MAİLRU PLAYER
def getMailVid():
    try: # iki iframe katmanından oluşuyor
        updateAlternatifler(0)
        print("\n\nMailru alternatifine göz atılıyor")
        alternatifler[sites.index("MAIL")].click()
        delay(4)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        iframe_2 = driver.find_element_by_css_selector("iframe")
        driver.switch_to.frame(iframe_2)
        url = driver.find_element_by_css_selector(".b-video-controls__mymail-link").get_attribute("href")
        checkVideo(url)
    except:
        print("Videoya erişilemiyor")
        return False
    else:
        oynat_indir(url)
    finally:
    	driver.switch_to.default_content()

# FEMBED PLAYER
def getFembedVid(): #Fembed nazlıdır, videoya bir kere tıklanılması gerekiyor linki alabilmek için
    try:
        updateAlternatifler(0)
        print("\n\nFembed alternatifine göz atılıyor")
        alternatifler[sites.index("FEMBED")].click()
        delay(4)
        play_button = driver.find_element_by_xpath("//div[@class='panel-body']/div[@class='video-icerik']/iframe")
        # Video url'sini ortaya çıkartmayı dene
        while True:
            play_button.click()
            delay(2)
            killed = killPopup()
            if not(killed):
                delay(1)
                play_button.click()
                break;
        #  Url 2 iframe katmaninin icinde sakli
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        iframe_2 = driver.find_element_by_css_selector("iframe")
        driver.switch_to.frame(iframe_2)
        url = driver.find_element_by_css_selector(".jw-media").get_attribute("src")
        checkVideo(url)
    except:
        print("Videoya erişilemiyor")
        return False
    else:
        oynat_indir(url)
    finally:
    	driver.switch_to.default_content()

def getMyviVid():
    try:
        updateAlternatifler(0)
        print("\n\nMyvi alternatifine göz atılıyor")
        alternatifler[sites.index("MYVI")].click()
        play_button = driver.find_element_by_xpath("//div[@class='panel-body']/div[@class='video-icerik']/iframe")
        play_button.click()
        delay(4.3)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        iframe_2 = driver.find_element_by_css_selector("iframe")
        driver.switch_to.frame(iframe_2)
        while True:
            try:
                driver.find_element_by_css_selector(".player-logo.player-logo-legacy")
            except: # kaybolduğunda
                break
        delay(1)
        play_button.click()
        url=driver.find_element_by_css_selector(".player-logo.player-logo-legacy").get_attribute("href")
        checkVideo(url)
    except:
        print("Videoya erişilemiyor")
        return False
    else:
        oynat_indir(url)
    finally:
    	driver.switch_to.default_content()

def deneAlternatifler():
    if sites.__contains__("RAPIDVIDEO"): #1
        getExternalVidOf("RAPIDVIDEO")
    if sites.__contains__("FEMBED"):
        getFembedVid()
    if sites.__contains__("MAIL"): #2
        getMailVid()
    if sites.__contains__("MYVI"): #3
        getMyviVid()
    for harici in HARICILER: #4,5,6,7 (satir 19)
        if sites.__contains__(harici):
            getExternalVidOf(harici)
    if sites.__contains__("TÜRKANİME"): #8
        getTurkanimeVid()



## !! MANUEL DEMO !! ##
hedef = input("HEDEF: ")

driver.get(hedef)
updateFansublar(1)

for i in range(0,len(fansublar)):
    fansublar[i].click()
    delay(1)
    killPopup()
    updateAlternatifler(1)
    delay(3)
    deneAlternatifler()
    driver.refresh()
    delay(1)
    updateFansublar(0)