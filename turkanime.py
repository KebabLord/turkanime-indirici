# -*- coding: utf-8 -*-
#
# Türkanime Video Player/Downloader v3
# https://github.com/Kebablord/turkanime-downloader
# GEREKSİNİMLER - geckodriver, python-selenium, mpv, youtube-dl,PyInquirer, httpx
#
from __future__ import print_function, unicode_literals
from time import sleep
from PyInquirer import style_from_dict, Token, prompt, Separator
from examples import custom_style_2
import multiprocessing
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from os import system,getpid,name,popen,mkdir,path
from sys import path as dizin
from atexit import register as register

dizin.insert(0, './api_arama')
from search_api import * # SevenOps'un arama yapma apisi

print('TürkAnimu İndirici v3')

ta = TurkAnime()
options = Options()
options.add_argument('--headless')

def ppprint(string):
    print(" "*54,end='\r')
    print(string,end='\r')

def at_exit():
    ppprint("Program kapatılıyor..")
    driver.quit()
register(at_exit)

ppprint("Sürücü başlatılıyor...")

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

ytdl_suffix = mpv_suffix = ""

ppprint(" ")


global hedef

HARICILER = [ # Türkanimenin yeni sekmede açtığı playerlar
        "UMPLOMP"
        "HDVID",
        "SENDVID",
        "STREAMANGO",
]

desteklenen_alternatifler = [ # Bütün desteklenen playerlar
    "SIBNET",
    "RAPIDVIDEO",
    "FEMBED",
    "OPENLOAD",
    "MAIL",
    "VK",
    "GPLUS",
    "MYVI",
    "TÜRKANİME",
    "ODNOKLASSNIKI"
] + HARICILER

def klasor():
    if not path.isdir('Downloads'):mkdir('Downloads')
    if not path.isdir('Downloads/'+foldername):mkdir('Downloads/'+foldername)
    return 'Downloads/'+foldername+'/'

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
    global ytdl_suffix,mpv_suffix
    if 'sibnet' in url_:
        ytdl_suffix += ' --config-location sibnet.conf'
        mpv_suffix += ' --ytdl-raw-options=config-location="sibnet.conf"'
    else:
        ytdl_suffix = mpv_suffix = ""
    if aksiyon.__contains__('indir'):
        #print(hedef)#DEBUG
        turkanime_link = hedef[1]
        filename = turkanime_link[turkanime_link.index("video/")+6:].replace("-","_").replace("/","")+".mp4"

        if (';' in url_) or ('&' in url_):
            url_ = "'"+url_+"'"
        else:
            url_ = '"'+url_+'"'
        #print(ytdl_prefix+"youtube-dl -o "+filename+" '"+url_+"'' "+ytdl_suffix)#+"> ./log")#DEBUG
        for i in range(0,4):
            basariStatus = system(ytdl_prefix+'youtube-dl -o '+klasor()+filename+' '+url_+' '+ytdl_suffix)#+"> ./log")
            if not(basariStatus):print("\nBaşarılı!");return True
    else:
        #print(mpv_prefix+"mpv "+url_+" > ./log")
        basariStatus = system(mpv_prefix+'mpv '+url_+' '+mpv_suffix)#+"> ./log")


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
    ppprint('Video yaşıyor mu kontrol ediliyor..')
    global resolutions,ytdl_suffix
    if 'sibnet' in url_:
            ytdl_suffix += ' --config-location sibnet.conf'
    else:ytdl_suffix = ""
    i = popen('youtube-dl -F "'+url_+'"'+ytdl_suffix)
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
            global mpv_suffix
            cevap = prompt([{
            'type': 'list',
            'name': 'res',
            'message': 'Çözünürlük seç:',
            'choices': [i[2] for i in resolutions]
            }
            ])['res']
            format_code = next(i[0] for i in resolutions if i[2]==cevap)
            ytdl_suffix += "-f "+str(format_code)
            mpv_suffix += "--ytdl-format "+str(format_code)+" "
        print('Videonun aktif olduğu doğrulandı.')
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
    killPopup()

# Video player listeleyici (fansub seçildikten sonra)
alternatifler = sites = []
def updateAlternatifler():
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
            sites.append({'name':alternatif.text,'disabled':'!'})
            continue
        sites.append(alternatif.text)
        #if n:print("  >"+alternatif.text)
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
        updateAlternatifler()
        ppprint(NYAN+" alternatifine göz atılıyor")
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
            ppprint("Bu kaynağa erişilemedi")
            return False
    else:
        #print("EXTERNAL IS SUCC")#DEBUG
        oynat_indir(url)
        return True
    


# TÜRKANİME PLAYER
def getTurkanimeVid():
    try: # iki iframe katmanından oluşuyor
        updateAlternatifler()
        ppprint("Türkanime alternatifine göz atılıyor")
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
        ppprint("Bu kaynağa erişilemedi")
        return False
    else:
        oynat_indir(url)
        return True

# MAİLRU PLAYER
def getMailVid():
    try: # iki iframe katmanından oluşuyor
        updateAlternatifler()
        ppprint("Mailru alternatifine göz atılıyor")
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
        ppprint("Bu kaynağa erişilemedi")
        return False
    else:
        oynat_indir(url)
        return True

# FEMBED PLAYER
def getFembedVid(): #Fembed nazlıdır, videoya bir kere tıklanılması gerekiyor linki alabilmek için
    try:
        updateAlternatifler()
        ppprint("Fembed alternatifine göz atılıyor")
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
        url = driver.find_element_by_css_selector(".jw-video").get_attribute("src")
        driver.switch_to.default_content()
        if not(checkVideo(url)): raise
    except:
        ppprint("Bu kaynağa erişilemedi")
        return False
    oynat_indir(url)
    return True

def getOLOADVid():
    updateAlternatifler()
    ppprint("Openload alternatifine göz atılıyor")
    alternatifler[sites.index("OPENLOAD")].click()
    sleep(3)
    driver.find_element_by_xpath("//div[@class='panel-body']/div[@class='video-icerik']/iframe").click()
    driver.switch_to.window(driver.window_handles[1])
    i = 0
    while i<7:
        sleep(1)
        try:
            driver.find_element_by_tag_name('body').click()
            sleep(2)
            while (len(driver.window_handles)>2):
                driver.switch_to.window(driver.window_handles[2])
                driver.close()
            driver.switch_to.window(driver.window_handles[1])
            sleep(2.3)    
            url = driver.find_elements_by_tag_name('video')[0].get_attribute('src')
            if not(url):
                raise
        except:
            i+=1
            continue
        else:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            ppprint("Video'yu yakalama başarılı!")
            oynat_indir(url)
            return True            
    driver.close()
    driver.switch_to.window(driver.window_handles[0])
    ppprint("Bu kaynağa erişilemedi")
    return False

def getMyviVid():
    try:
        updateAlternatifler()
        ppprint("Myvi alternatifine göz atılıyor")
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
        ppprint("Bu kaynağa erişilemedi")
        return False
    else:
        oynat_indir(url)
        return True        

def getVKvid():
    try:
        updateAlternatifler()
        ppprint("Vk alternatifine göz atılıyor")
        alternatifler[sites.index("VK")].click()
        sleep(6)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        url = driver.find_element_by_tag_name("iframe").get_attribute("src")
        url = url[url.index("?")+1:]
        driver.switch_to.default_content()
        if not(checkVideo(url)): raise
    except:
            ppprint("Bu kaynağa erişilemedi")
            return False
    else:
        oynat_indir(url)
        return True

def getGPLUSvid():
    try: # iki iframe katmanından oluşuyor
        updateAlternatifler()
        ppprint("GPLUS alternatifine göz atılıyor")
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
        ppprint("Bu kaynağa erişilemedi")
        return False
    else:
        oynat_indir(url)
        return True

def getOKRUvid():
    try: # iki iframe katmanından oluşuyor
        updateAlternatifler()
        ppprint("OKRU alternatifine göz atılıyor")
        alternatifler[sites.index("ODNOKLASSNIKI")].click()
        sleep(4)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        url = driver.find_element_by_xpath('//object/param[@name="flashvars"]').get_attribute('value')
        url = "http://www.ok.ru/videoembed/"+url[url.index('mid%3D')+6:url.index('&locale=tr')]
        driver.switch_to.default_content()
        if not(checkVideo(url)): raise
    except:
        ppprint("Bu kaynağa erişilemedi")
        return False
    else:
        oynat_indir(url)
        return True

def getSIBNETvid():
    try: # iki iframe katmanından oluşuyor
        updateAlternatifler()
        ppprint("SIBNET alternatifine göz atılıyor")
        alternatifler[sites.index("SIBNET")].click()
        sleep(4)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        iframe_2 = driver.find_element_by_css_selector("iframe")
        driver.switch_to.frame(iframe_2)
        url = driver.find_elements_by_tag_name('meta')[7].get_attribute('content')
        driver.switch_to.default_content()
        if not(checkVideo(url)): raise
    except:
        ppprint("Bu kaynağa erişilemedi")
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
    elif nyan=="MAIL": #2
        err = getMailVid()
    elif nyan=="MYVI": #3
        err = getMyviVid()
    elif nyan=="VK":
        err = getVKvid()
    elif nyan=="TÜRKANİME": #8
        err = getTurkanimeVid()
    elif nyan=="GPLUS":
        err = getGPLUSvid()
    elif nyan=="ODNOKLASSNIKI":
        err = getOKRUvid()
    elif nyan=="OPENLOAD":
        err = getOLOADVid()
    elif nyan=="SIBNET":
        err = getSIBNETvid()
    else:
        err = getExternalVidOf(nyan)
    return err

def deneAlternatifler(n):
    err = False
    if n==1:
        if sites.__contains__("SIBNET"): #1
            err = getSIBNETvid()
            if err:return err
        if sites.__contains__("RAPIDVIDEO"): #2
            err = getExternalVidOf("RAPIDVIDEO")
            if err:return err
        if sites.__contains__("FEMBED"): #3
            err = getFembedVid()
            if err:return err
        if sites.__contains__("OPENLOAD"): #4
            err = getOLOADVid()
            if err:return err
        if sites.__contains__("MAIL"): #5
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
        if sites.__contains__("ODNOKLASSNIKI"): #8
            err = getOKRUvid()
            if err:return err
    return err

tum_sonuclar = []
def sonuclar(answers):
    global tum_sonuclar,aksiyon
    aksiyon = answers['aksiyon']
    tum_sonuclar = ta.anime_ara(answers['arama'])
    while not(tum_sonuclar):
            tum_sonuclar = ta.anime_ara(input("Sonuç bulunamadı, tekrar deneyin: "))
    if len(tum_sonuclar)==1:
        tum_sonuclar[0][0]=tum_sonuclar[0][1].replace('-',' ').capitalize()
    sonux = []
    for i in tum_sonuclar:
        sonux.append(i[0])
    return sonux

tum_bolumler = []
def bolumler(answers):
    global tum_bolumler,foldername
    for i in tum_sonuclar:
        if answers['isim']==i[0]:
            foldername = i[1].replace('-','_')
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
        'message': 'İşlemi seç',
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
ppprint(" ")
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
    ppprint(hedef[0]+'.bölüme göz atılıyor..')
    driver.get(hedef[1])
    sleep(1.5)
    if (len(hedefler)>1) and aksiyon.__contains__('indir'):
        updateFansublar() # İlk olarak kaliteli alternatifleri dener
        #print("deneniyor 1")#DEBUG
        for fansub in fansublar:
            #print(fansub)#DEBUG
            fansub[1].click()
            sleep(2.5)
            updateAlternatifler()
            err = deneAlternatifler(1)
            #print("alternatifin döndürdüğü cevap:"+str(err))#DEBUG
            if err:break
            updateFansublar()
        if err:continue
        updateFansublar() # Ardından 2. derece alternatifleri dener
        for fansub in fansublar:
            #print(fansub)
            fansub[1].click()
            sleep(2.5)
            updateAlternatifler()
            err = deneAlternatifler(2)
            updateFansublar()
        if not(err):print(hedef[0]+".bölüm indirilemedi, ya site kötü durumda yada program. Pas geçiliyor.")
    else:
        while (True and not(flag)):
            updateFansublar()
            funsub = prompt([{
                'type': 'list',
                'name': 'fansub',
                'message': 'Fansub seç',
                'choices': [i[0] for i in fansublar]+["Geri dön"]
            }])['fansub']
            if funsub=="Geri dön": break
            btn = [i[1] for i in fansublar if i[0]==funsub][0]
            btn.click()
            while True:
                updateAlternatifler()
                kaynax = prompt([{
                    'type': 'list',
                    'name': 'kaynak',
                    'message': 'Kaynak seç',
                    'choices': sites+["Geri dön"]
                }])['kaynak']
                if kaynax=="Geri dön": break
                alternatifler[sites.index(kaynax)].click
                ppprint("\n\nVideo hazırlanıyor..")
                err = deneAlternatif(kaynax)
                #print("err "+str(err)) #DEBUG
                if not(err): continue # Eğer error aldıysak kullanıcıya farklı bi alternatif için şans ver
                flag = True
                break
        if hedef != hedefler[-1]:
            ppprint("Sıradaki bölüme geçiliyor..")
