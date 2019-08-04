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
from PyInquirer import style_from_dict, Token, prompt, Separator
from examples import custom_style_2
import multiprocessing
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from os import system,getpid,name,popen
from sys import path
from atexit import register as register

path.insert(0, './api_arama')
from search_api import * # SevenOps'un arama yapma apisi

ta = TurkAnime()
options = Options()
options.add_argument('--headless')

def at_exit():
    print("Program kapatılıyor..",end='\r')
    driver.quit()
register(at_exit)

print("Sürücü başlatılıyor...",end="\r")

if name=="nt":
    driver = webdriver.Firefox(options=options,executable_path=r'geckodriver.exe')
    #driver = webdriver.PhantomJS('phantomjs.exe')
    ytdl_prefix=""
    mpv_prefix=""
else:
    driver = webdriver.Firefox(options=options)
    #driver = webdriver.PhantomJS()
    ytdl_prefix=""
    mpv_prefix=""

ytdl_infix = mpv_infix = ""

print(len("Sürücü başlatılıyor...")*" ",end="\r")


global hedef

HARICILER = [ # Türkanimenin yeni sekmede açtığı playerlar
        "UMPLOMP"
        "HDVID",
        "SENDVID",
        "STREAMANGO",
]

desteklenen_alternatifler = [ # Bütün desteklenen playerlar
    "RAPIDVIDEO",
    "FEMBED",
    "MAIL",
    "VK",
    "GPLUS",
    "MYVI",
    "TÜRKANİME"
] + HARICILER

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
        #print(hedef)#DEBUG
        turkanime_link = hedef[1]
        filename = turkanime_link[turkanime_link.index("video/")+6:].replace("-","_").replace("/","")+".mp4 "
        #print(ytdl_prefix+"youtube-dl -o "+filename+url_+" "+ytdl_infix)#+"> ./log")#DEBUG
        for i in range(0,4):
            basariStatus = system(ytdl_prefix+"youtube-dl -o "+filename+url_+" "+ytdl_infix)#+"> ./log")
            if not(basariStatus):print("SUCCESS");return True
    else:
        #print(mpv_prefix+"mpv "+url_+" > ./log")
        basariStatus = system(mpv_prefix+"mpv "+url_+" "+mpv_infix)#+"> ./log")


"""def res_choices(n):
    return [i[2] for i in resolutions]

res_s = [
    {
        'type': 'list',
        'name': 'res',
        'message': 'Çözünürlük seç:',
        'choices': [i[2] for i in resolutions]
    }
]"""

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
        if (len([i[2] for i in resolutions])>1) and (aksiyon.__contains__('izle')):
            global mpv_infix,ytdl_infix
            cevap = prompt([{
            'type': 'list',
            'name': 'res',
            'message': 'Çözünürlük seç:',
            'choices': [i[2] for i in resolutions]
            }
            ])['res']
            format_code = next(i[0] for i in resolutions if i[2]==cevap)
            ytdl_infix += "-f "+str(format_code)
            mpv_infix += "--ytdl-format "+str(format_code)+" "
        return True
    else:
        return False



# Fansub listeleyici
fansublar = []
def updateFansublar():
    global fansublar
    fansublar.clear()
#    fansublar = driver.find_elements_by_xpath("//div[@class='panel-body']/div[@class='pull-right']/button")
    for sub in driver.find_elements_by_css_selector("div.panel-body div.pull-right button"):
        fansublar.append([sub.text,sub])
        if sub=="": raise
    fansublar.append(["Geri dön","0"])
    killPopup()

# Video player listeleyici (fansub seçildikten sonra)
alternatifler = sites = []
def updateAlternatifler(n):
    killPopup()
    global alternatifler,sites
    sleep(1.5)
    #if n:print("\n\nMEVCUT KAYNAKLAR:")
    alternatifler = driver.find_elements_by_xpath("//div[@class='panel-body']/div[@class='btn-group']/button") # > [12,334,34534]
    """while True:
        alternatifler = driver.find_elements_by_xpath("//div[@class='panel-body']/div[@class='btn-group']/button")
        if alternatifler:
            break
        sleep(1)
        print("retry")"""
    sites.clear()
    #! "alternatifler" listesinde butonların html kodları ; "sites" listesinde butonların isimleri var
    for alternatif in alternatifler:
        if not(desteklenen_alternatifler.__contains__(alternatif.text)):
            sites.append({'name':alternatif.text,'disabled':'Henüz desteklenmiyor'})
            continue
        sites.append(alternatif.text)
        #if n:print("  >"+alternatif.text)
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
    try:
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
        if not(checkVideo(url)): raise
    except: # HTML DOSYASI HATA VERİRSE
            print("Videoya erişilemiyor",end='\r')
            return False
    else:
        #print("EXTERNAL IS SUCC")#DEBUG
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
    try:
        updateAlternatifler(0)
        print("Vk alternatifine göz atılıyor",end="\r")
        alternatifler[sites.index("VK")].click()
        sleep(4)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        url = driver.find_element_by_tag_name("iframe").get_attribute("src")
        url = url[url.index("?")+1:]
        driver.switch_to.default_content()
        if not(checkVideo(url)): raise
    except:
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
        if not(checkVideo(url)): raise
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


def deneAlternatif(nyan):
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

def deneAlternatifler(n):
    if n==1:
        if sites.__contains__("RAPIDVIDEO"): #1
            err = getExternalVidOf("RAPIDVIDEO")
            if err:return err
        if sites.__contains__("FEMBED"):
            err = getFembedVid()
            if err:return err
        if sites.__contains__("MAIL"): #2
            err = getMailVid()
            if err:return err
    else:
        if sites.__contains__("VK"):
            err = getVKvid()
            if err:return err
        if sites.__contains__("GPLUS"):
            err = getGPLUSvid()
            if err:return err
        if sites.__contains__("MYVI"): #3
            err = getMyviVid()
            if err:return err
        for harici in HARICILER: #4,5,6,7 (satir 19)
            if sites.__contains__(harici):
                err = getExternalVidOf(harici)
                if err:return err
        if sites.__contains__("TÜRKANİME"): #8
            err = getTurkanimeVid()
            if err:return err
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

"""class getChoices:
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
]"""


for hedef in hedefler:
    flag = False
    print(hedef[0]+'.bölüme göz atılıyor..          ',end='\r')
    driver.get(hedef[1])
    sleep(1.5)
    if (len(hedefler)>1) and aksiyon.__contains__('indir'):
        updateFansublar() # İlk olarak kaliteli alternatifleri dener
        #print("deneniyor 1")#DEBUG
        for fansub in fansublar:
            fansub[1].click()
            sleep(2.5)
            updateAlternatifler(0)
            err = deneAlternatifler(1)
            #print("alternatifin döndürdüğü cevap:"+str(err))#DEBUG
            if err:break
        if err:continue
        updateFansublar() # Ardından 2. derece alternatifleri dener
        for fansub in fansublar:
            fansub[1].click()
            sleep(2.5)
            updateAlternatifler(0)
            err = deneAlternatifler(2)
        if not(err):print(hedef[0]+".bölüm indirilemedi, ya site kötü durumda yada program. Pas geçiliyor.")
    else:
        while (True and not(flag)):
            updateFansublar()
            funsub = prompt([{
                'type': 'list',
                'name': 'fansub',
                'message': 'Fansub seç',
                'choices': [i[0] for i in fansublar]
            }])['fansub']
            if funsub=="Geri dön": break
            btn = [i[1] for i in fansublar if i[0]==funsub][0]
            btn.click()
            while True:
                updateAlternatifler(0)
                kaynax = prompt([{
                    'type': 'list',
                    'name': 'kaynak',
                    'message': 'Kaynak seç',
                    'choices': sites
                }])['kaynak']
                if kaynax=="Geri dön": break
                alternatifler[sites.index(kaynax)].click
                print("Video hazırlanıyor..",end="\r")
                err = deneAlternatif(kaynax)
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
    