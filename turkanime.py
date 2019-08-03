# Türkanime Video Player/Downloader 2.5.0

# GEREKSİNİMLER - geckodriver, python-selenium, mpv, youtube-dl

# YAPILACAKLAR LİSTESİ
"""
- Openload alternatifi eklenicek
- Cli geliştirilecek
"""
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals
from time import sleep
from random import randint as xd
from pprint import pprint
from PyInquirer import style_from_dict, Token, prompt, Separator
from examples import custom_style_2
import multiprocessing
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from os import system,getpid,name,popen
from sys import path

path.insert(0, './api_arama')
from search_api import * # SevenOps'un arama yapma apisi

ta = TurkAnime()
options = Options()
options.add_argument('--headless')

print("Sürücü başlatılıyor...",end="\r")

if name=="nt":
    driver = webdriver.Firefox(options=options,executable_path=r'geckodriver.exe')
    #driver = webdriver.PhantomJS('phantomjs.exe')
    ytdl_prefix=""
    mpv_prefix=""
else:
    driver = webdriver.Firefox(options=options)
    ytdl_prefix=""
    mpv_prefix=""

ytdl_infix = mpv_infix = ""

print(len("Sürücü başlatılıyor...")*" ",end="\r")


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


aksiyon = ""
def oynat_indir(url_):
    driver.get("about:blank")
    if aksiyon.__contains__('indir'):
        filename = hedef[hedef.index("video/")+6:].replace("-","_").replace("/","")+".mp4 "
        basariStatus = system(ytdl_prefix+"youtube-dl -o "+filename+url_+" "+ytdl_infix+"> ./log")
    else:
        #print(mpv_prefix+"mpv "+url_+" > ./log")
        basariStatus = system(mpv_prefix+"mpv "+url_+" "+mpv_infix+"> ./log")


def res_choices(n):
    return [i[2] for i in resolutions]

res_s = [
    {
        'type': 'list',
        'name': 'res',
        'message': 'Çözünürlük seç:',
        'choices': res_choices
    }
]

resolutions = []
def checkVideo(url_):
    global resolutions
    i = popen('youtube-dl -F "'+url_+'"')
    data = i.read();
    status = i.close()
    if status==None:
        data = data[data.index('note')+5:].split()
        if data.__contains__('[download]'):data = data[:data.index('[download]')]
        if data.__contains__('(best)'): data.remove('(best)')
        resolutions.clear()
        for i in range(0,int(len(data)/3)):
            resolutions.append(data[i*3:i*3+3])
        if len([i[2] for i in resolutions])>1:
            global mpv_infix,ytdl_infix
            cevap = prompt(res_s)['res']
            format_code = next(i[0] for i in resolutions if i[2]==cevap)
            ytdl_infix += "-f "+str(format_code)
            mpv_infix += "--ytdl-format "+str(format_code)+" "
        return True
    else:
        return False



# Fansub listeleyici
fansublar = []
def updateFansublar(n):
    global fansublar
    fansublar.clear()
#    fansublar = driver.find_elements_by_xpath("//div[@class='panel-body']/div[@class='pull-right']/button")
    for sub in driver.find_elements_by_css_selector("div.panel-body div.pull-right button"):
        fansublar.append([sub.text,sub])
    fansublar.append(["Geri dön","0"])
    """if n:
        print("\nMEVCUT FANSUBLAR:")
        for fansub in fansublar:
            print("  >"+fansub.text)"""
    killPopup()

# Video player listeleyici (fansub seçildikten sonra)
alternatifler = sites = []
def updateAlternatifler(n):
    killPopup()
    global alternatifler,sites
    sleep(1.5)
    if n:print("\n\nMEVCUT KAYNAKLAR:")
    alternatifler = driver.find_elements_by_xpath("//div[@class='panel-body']/div[@class='btn-group']/button")
    """while True:
        alternatifler = driver.find_elements_by_xpath("//div[@class='panel-body']/div[@class='btn-group']/button")
        if alternatifler:
            break
        sleep(1)
        print("retry")"""
    sites.clear()
    #! "alternatifler" listesinde butonların html kodları ; "sites" listesinde butonların isimleri var
    for alternatif in alternatifler:
        sites.append(alternatif.text)
        if n:print("  >"+alternatif.text)
    sites.append("Geri dön")
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
    updateAlternatifler(0)
    print("\n\n"+NYAN+" alternatifine göz atılıyor",end="\r")
    alternatifler[sites.index(NYAN)].click() #alternatife tıkla
    sleep(5)
    """while True:
        if driver.find_elements_by_css_selector(".video-icerik iframe"):
            break
        sleep(1)"""
    iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe") #iframe'in içine gir
    driver.switch_to.frame(iframe_1)
    url = driver.find_element_by_css_selector("#link").get_attribute("href") #linki ceple
    driver.switch_to.default_content()
    if not(checkVideo(url)):
        print("Videoya erişilemiyor",end='\r')
        return False
    else:
        oynat_indir(url)
        return True
    


# TÜRKANİME PLAYER
def getTurkanimeVid():
    try: # iki iframe katmanından oluşuyor
        updateAlternatifler(0)
        print("\n\nTürkanime alternatifine göz atılıyor",end="\r")
        alternatifler[sites.index("TÜRKANİME")].click()
        sleep(4)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        iframe_2 = driver.find_element_by_css_selector("iframe")
        driver.switch_to.frame(iframe_2)
        url = driver.find_element_by_css_selector(".jw-media").get_attribute("src")
        driver.switch_to.default_content()
        if not(checkVideo(url)): raise
    except:
        print("Videoya erişilemiyor",end='\r')
        return False
    else:
        oynat_indir(url)
        return True

# MAİLRU PLAYER
def getMailVid():
    try: # iki iframe katmanından oluşuyor
        updateAlternatifler(0)
        print("\n\nMailru alternatifine göz atılıyor",end="\r")
        alternatifler[sites.index("MAIL")].click()
        sleep(8)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        iframe_2 = driver.find_element_by_css_selector("iframe")
        driver.switch_to.frame(iframe_2)
        url = driver.find_element_by_css_selector(".b-video-controls__mymail-link").get_attribute("href")
        driver.switch_to.default_content()
        if not(checkVideo(url)): raise
    except:
        print("Videoya erişilemiyor",end='\r')
        return False
    else:
        oynat_indir(url)
        return True

# FEMBED PLAYER
def getFembedVid(): #Fembed nazlıdır, videoya bir kere tıklanılması gerekiyor linki alabilmek için
    try:
        updateAlternatifler(0)
        print("\n\nFembed alternatifine göz atılıyor",end="\r")
        alternatifler[sites.index("FEMBED")].click()
        sleep(4)
        play_button = driver.find_element_by_xpath("//div[@class='panel-body']/div[@class='video-icerik']/iframe")
        # Video url'sini ortaya çıkartmayı dene
        while True:
            play_button.click()
            sleep(2)
            killed = killPopup()
            if not(killed):
                sleep(1)
                play_button.click()
                break;
        #  Url 2 iframe katmaninin icinde sakli
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        iframe_2 = driver.find_element_by_css_selector("iframe")
        driver.switch_to.frame(iframe_2)
        url = driver.find_element_by_css_selector(".jw-media").get_attribute("src")
        driver.switch_to.default_content()
        if not(checkVideo(url)): raise
    except:
        print("Videoya erişilemiyor",end='\r')
        return False
    else:
        oynat_indir(url)
        return True

def getMyviVid():
    try:
        updateAlternatifler(0)
        print("\n\nMyvi alternatifine göz atılıyor",end="\r")
        alternatifler[sites.index("MYVI")].click()
        sleep(3.5)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        iframe_2 = driver.find_element_by_tag_name("iframe")
        driver.switch_to.frame(iframe_2)
        url = driver.find_elements_by_tag_name("link")[0].get_attribute("href")
        driver.switch_to.default_content()
        if not(checkVideo(url)): raise
    except:
        print("Videoya erişilemiyor",end='\r')
        return False
    else:
        oynat_indir(url)
        return True        

def getVKvid():
    updateAlternatifler(0)
    print("Vk alternatifine göz atılıyor",end="\r")
    alternatifler[sites.index("VK")].click()
    sleep(4)
    iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
    driver.switch_to.frame(iframe_1)
    url = driver.find_element_by_tag_name("iframe").get_attribute("src")
    url = url[url.index("?")+1:]
    driver.switch_to.default_content()
    if not(checkVideo(url)):
        print("Videoya erişilemedi",end="\r")
        return False
    else:
        oynat_indir(url)
        return True

def getGPLUSvid():
    try: # iki iframe katmanından oluşuyor
        updateAlternatifler(0)
        print("\n\nGPLUS alternatifine göz atılıyor",end="\r")
        alternatifler[sites.index("GPLUS")].click()
        sleep(4)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        iframe_2 = driver.find_element_by_css_selector("iframe")
        driver.switch_to.frame(iframe_2)
        url = driver.find_element_by_css_selector(".jw-media").get_attribute("src")
        driver.switch_to.default_content()
        checkVideo(url)
    except:
        print("Videoya erişilemiyor",end='\r')
        return False
    else:
        oynat_indir(url)
        return True

"""
def deneAlternatifler():
    if sites.__contains__("RAPIDVIDEO"): #1
        getExternalVidOf("RAPIDVIDEO")
    if sites.__contains__("FEMBED"):
        getFembedVid()
    if sites.__contains__("MAIL"): #2
        getMailVid()
    if sites.__contains__("MYVI"): #3
        getMyviVid()
    if sites.__contains__("VK"):
        getVKvid()
    for harici in HARICILER: #4,5,6,7 (satir 19)
        if sites.__contains__(harici):
            getExternalVidOf(harici)
    if sites.__contains__("TÜRKANİME"): #8
        getTurkanimeVid()
"""
def deneAlternatifler(nyan):
    if nyan=="FEMBED":
        err = getFembedVid()
    if nyan=="MAIL": #2
        err = getMailVid()
    if nyan=="MYVI": #3
        err = getMyviVid()
    if nyan=="VK":
        err = getVKvid()
    if nyan=="TÜRKANİME": #8
        err = getTurkanimeVid()
    if nyan=="GPLUS":
        err = getGPLUSvid()
    else:
        err = getExternalVidOf(nyan)
    return err



tum_sonuclar = []
def sonuclar(answers):
    global tum_sonuclar,aksiyon
    aksiyon = answers['aksiyon']
    tum_sonuclar = ta.anime_ara(answers['arama'])
    if not(tum_sonuclar):
        a = input("Sonuç bulunamadı, animenin tam adını girin: ")
        tum_sonuclar=[[a,a.replace(' ','-').replace('I','i').replace(':','').replace('!','')]]
    sonux = []
    for i in tum_sonuclar:
        sonux.append(i[0])
    return sonux

tum_bolumler = []
def bolumler(answers):
    global tum_bolumler
    for i in tum_sonuclar:
        if answers['isim']==i[0]:
            tum_bolumler=ta.bolumler(i[1])
            break
    sonux = []
    for i in tum_bolumler:
        sonux.append({'name':i[0]})
    return sonux

giris_s = [
    {
        'type': 'list',
        'name': 'aksiyon',
        'message': 'fu-TA v2',
        'choices': [
            'Anime izle',
            'Anime indir'
        ]
    },
    {
        'type': 'input',
        'name': 'arama',
        'message': 'Animeyi ara',
    },
    {
        'type': 'list',
        'name': 'isim',
        'message': 'Animeyi seç',
        'choices': sonuclar,
    },
    {
        'type': 'checkbox',
        'message': 'Bölümleri seç',
        'name': 'bolum',
        'choices': bolumler
    }

]

#answers = prompt(questions, style=custom_style_2)
giris_c = prompt(giris_s)

hedefler = []
prefix_hedefler = 'https://turkanime.tv/video/'
for i in tum_bolumler:
    if giris_c['bolum'].__contains__(i[0]):
        hedefler.append([i[0],prefix_hedefler+i[1]])
print("")
#pprint(hedefler)

class getChoices:
    def sub(n):
        return [i[0] for i in fansublar]
    def src(n):
        return sites
    def res(n):
        return 

fansub_s = [
    {
        'type': 'list',
        'name': 'fansub',
        'message': 'Fansub seç',
        'choices': getChoices.sub
    }
]

kaynak_s = [
    {
        'type': 'list',
        'name': 'kaynak',
        'message': 'Kaynak seç',
        'choices': getChoices.src
    }
]


for hedef in hedefler:
    flag = False
    print(hedef[0]+'.bölüme göz atılıyor..',end='\r')
    driver.get(hedef[1])
    sleep(1.5)
    while (True and not(flag)):
        updateFansublar(0)
        funsub = prompt(fansub_s)['fansub']
        if funsub=="Geri dön": break
        btn = [i[1] for i in fansublar if i[0]==funsub][0]
        btn.click()
        while True:
            updateAlternatifler(0)
            kaynax = prompt(kaynak_s)['kaynak']
            if kaynax=="Geri dön": break
            alternatifler[sites.index(kaynax)].click
            print("Video hazırlanıyor..",end="\r")
            err = deneAlternatifler(kaynax)
            #print("err "+str(err)) #debug
            if not(err): continue # Eğer error aldıysak kullanıcıya farklı bi alternatif için şans ver
            flag = True
            break
    if hedef != hedefler[-1]:
        print("Sıradaki bölüme geçiliyor..",end='\r')

"""
    updateAlternatifler(0)
    kaynak = prompt(kaynak_s)['']
    next(i[0] for i in resolutions if i[2]==a)"""
