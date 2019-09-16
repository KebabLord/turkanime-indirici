#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Türkanime Video Player/Downloader v3
# https://github.com/Kebablord/turkanime-downloader
# EK GEREKSİNİMLER - geckodriver, mpv, youtube-dl
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

DIR=path.realpath(__file__)
DIR="/".join(DIR.split("/")[0:-1])
DIR=path.join(DIR,'api_arama')
#print("Api'nin konumu: "+DIR)#DEBUG

dizin.insert(0,DIR)
from search_api import * # SevenOps'un arama yapma apisi

print('TürkAnimu İndirici - github/Kebablord')

ta = TurkAnime()
options = Options()
options.add_argument('--headless')

def ppprint(string): ## Statik yazı printleme fonksiyonu
    print(" "*54,end='\r')
    print(string,end='\r')

def at_exit(): ## Program kapatıldığında
    ppprint("Program kapatılıyor..")
    driver.quit()
register(at_exit)

ppprint("Sürücü başlatılıyor...")

if name is 'nt': # WINDOWS
    driver = webdriver.Firefox(options=options,executable_path=r'geckodriver.exe')
    #driver = webdriver.PhantomJS('phantomjs.exe')
else:            # LINUX
    driver = webdriver.Firefox(options=options)
    #driver = webdriver.PhantomJS()

#ytdl_suffix = mpv_suffix = ""
ppprint(" ")


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

# ÇÖZÜNÜRLÜK FORMAT KODLARI
rezs = [
    '360p',"'worstvideo[height>=360]+bestaudio/worst[height>=360]'",
    '480p',"'worstvideo[height>=480]+bestaudio/worst[height>=480]'",
    '720p',"'bestvideo[height<=720]+bestaudio/best[height<=720]'",
    'En iyi',"'best'"]

mpv_mod = False # Kaydetme modu fabrika ayarı
if path.isfile('ayarlar.conf'): # ÖNCEDEN YAPILAN AYARLARI İMPORTLA
    with open('ayarlar.conf','r') as f:
        for ayar in [i for i in f.readlines() if i[0]!='#']:
            exec(ayar)
        f.close()
#    ppprint(vars()['oto_dizin'])

def klasor():
    if 'oto_dizin' in globals():
        kayitfolder = path.join(oto_dizin,sub_foldername)
    else:
        if not path.isdir('Downloads'):mkdir('Downloads')
        kayitfolder = path.join('Downloads',sub_foldername)
    if not path.isdir(kayitfolder):mkdir(kayitfolder)
    return kayitfolder

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
    if 'sibnet' in url_:
        ytdl_suffix = ' --config-location sibnet.conf'
        mpv_suffix = ' --ytdl-raw-options=config-location="sibnet.conf"'
    else:ytdl_suffix = mpv_suffix = ""

    if (';' in url_) or ('&' in url_):url_ = "'"+url_+"'"
    else:url_ = '"'+url_+'"'

#   (birden fazla çözünürlük varsa ve izleme modundaysa yada indirme modunda yanlız bir video seçilmişse)
    if (('izle' in aksiyon) or (len(hedefler)<2)):
        if (len([i[2] for i in resolutions])>4):
            cevap = prompt([{
            'type': 'list',
            'name': 'res',
            'message': 'Çözünürlük seç:',
            'choices': ['360p','480p','720p','En iyi']
            }
            ])['res']
            format_code = rezs[rezs.index(cevap)+1]
            ytdl_suffix += "-f "+format_code+" "
            mpv_suffix += "--ytdl-format "+format_code+" "
            #print(mpv_suffix,ytdl_suffix,format_code)#DEBUGx
        elif (len([i[2] for i in resolutions])>1):
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
            #print(mpv_suffix,ytdl_suffix,format_code)#DEBUGx
    elif 'oto_cozunurluk' in vars():
        ytdl_suffix += "-f "+oto_cozunurluk
        mpv_suffix += "--ytdl-format "+oto_cozunurluk


    turkanime_link = hedef[1]
    filename = turkanime_link[turkanime_link.index("video/")+6:].replace("-","_").replace("/","")+".mp4"

    if 'mpv_mod' in globals() and mpv_mod:
        mpv_suffix += ' --record-file='+path.join(klasor(),filename)

    if aksiyon.__contains__('indir'):
        for i in range(1,4):
            basariStatus = system('youtube-dl --no-warnings -o '+path.join(klasor(),filename)+' '+url_+' '+ytdl_suffix)#+"> ./log")
            #print('youtube-dl --no-warnings -o '+path.join(klasor(),filename)+' '+url_+' '+ytdl_suffix)#DEBUGx
            if not(basariStatus):
                print("\nİŞLEM BAŞARILI!\n")
                driver.get("about:blank")
                return True
            print("[durum] "+str(i)+".deneme")
        print("Farklı bir alternatife geçiliyor");return False
    else:
        #print('mpv '+url_+' '+mpv_suffix)#debugx
        basariStatus = system('mpv '+url_+' '+mpv_suffix)#+"> ./log")
        if not(basariStatus):
            driver.get("about:blank")
            return True
        else:return False


resolutions = []
def checkVideo(url_):
    ppprint('Video yaşıyor mu kontrol ediliyor..')
    global resolutions
    if 'sibnet' in url_:
            ytdl_suffix = ' --config-location sibnet.conf'
    else:ytdl_suffix = ""
    i = popen('youtube-dl --no-warnings -F "'+url_+'"'+ytdl_suffix)
    data = i.read();
    status = i.close()
    if status==None:
        data = data[data.index('note')+5:].split()
        if data.__contains__('[download]'):data = data[:data.index('[download]')]
        if data.__contains__('(best)'): data.remove('(best)')
        resolutions.clear()
        for i in range(0,int(len(data)/3)):
            resolutions.append(data[i*3:i*3+3])
        print('Videonun aktif olduğu doğrulandı.')
        return True
    else:
        return False



# Fansub listeleyici
fansublar = []
def updateFansublar():
    sleep(4)
    ppprint('Fansublar güncelleniyor...')
    driver.switch_to.default_content()
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
    ppprint('Alternatifler güncelleniyor..')
    driver.switch_to.default_content()
    killPopup()
    global alternatifler,sites
    sleep(1.5)
    #if n:print("\n\nMEVCUT KAYNAKLAR:")
    alternatifler = driver.find_elements_by_xpath("//div[@class='panel-body']/div[@class='btn-group']/button") # > [12,334,34534]
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
        #driver.switch_to.default_content()
        if not(checkVideo(url)): raise
    except: # HTML DOSYASI HATA VERİRSE
            print(NYAN+" alternatifindeki video silinmiş veya arızalı.")
            return False
    else:
        #print("EXTERNAL IS SUCC")#DEBUG
        if oynat_indir(url): return True
        else: return False
    


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
        #driver.switch_to.default_content()
        if not(checkVideo(url)): raise
    except:
        print("TürkAni alternatifindeki video silinmiş veya arızalı.")
        return False
    else:
        if oynat_indir(url): return True
        else: return False

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
        #driver.switch_to.default_content()
        if not(checkVideo(url)): raise
    except:
        print("Mail alternatifindeki video silinmiş veya arızalı.")
        return False
    else:
        if oynat_indir(url): return True
        else: return False

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
        #driver.switch_to.default_content()
        if not(checkVideo(url)): raise
    except:
        print("Fembed alternatifindeki video silinmiş veya arızalı.")
        return False
    if oynat_indir(url): return True
    else: return False

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
            if oynat_indir(url): return True
            else: return False
    driver.close()
    driver.switch_to.window(driver.window_handles[0])
    print("OpenLoad alternatifindeki video silinmiş veya arızalı.")
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
        #driver.switch_to.default_content()
        if not(checkVideo(url)): raise
    except:
        print("Myvi alternatifindeki video silinmiş veya arızalı.")
        return False
    else:
        if oynat_indir(url): return True
        else: return False    

def getVKvid():
    try:
        updateAlternatifler()
        ppprint("Vk alternatifine göz atılıyor")
        alternatifler[sites.index("VK")].click()
        sleep(6)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        iframe_2 = driver.find_element_by_tag_name("iframe")
        driver.switch_to.frame(iframe_2)
        url = driver.find_element_by_css_selector('.videoplayer_btn_vk').get_attribute('href')
        #driver.switch_to.default_content()
        if not(checkVideo(url)): raise
    except:
            print("Vk alternatifindeki video silinmiş veya arızalı.")
            return False
    else:
        if oynat_indir(url): return True
        else: return False

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
        #driver.switch_to.default_content()
        if not(checkVideo(url)): raise
    except:
        print("G+ alternatifindeki video silinmiş veya arızalı.")
        return False
    else:
        if oynat_indir(url): return True
        else: return False

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
        #driver.switch_to.default_content()
        if not(checkVideo(url)): raise
    except:
        print("Ok.ru alternatifindeki video silinmiş veya arızalı.")
        return False
    else:
        if oynat_indir(url): return True
        else: return False

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
        #driver.switch_to.default_content()
        if not(checkVideo(url)): raise
    except:
        print("Sibnet alternatifindeki video silinmiş veya arızalı.")
        return False
    else:
        if oynat_indir(url): return True
        else: return False


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
    global tum_sonuclar
    while True:
        try:
            tum_sonuclar = ta.anime_ara(answers['arama'])
            break
        except:
        	pass
    while not(tum_sonuclar):
            tum_sonuclar = ta.anime_ara(input("Sonuç yok, tekrar deneyin. Menü için ctrl-c "))
    if len(tum_sonuclar)==1:
        tum_sonuclar[0][0]=tum_sonuclar[0][1].replace('-',' ').capitalize()
    sonux = []
    for i in tum_sonuclar:
        sonux.append(i[0])
    return sonux

tum_bolumler = []
def bolumler(answers):
    global tum_bolumler,sub_foldername
    for i in tum_sonuclar:
        if answers['isim']==i[0]:
            sub_foldername = i[1].replace('-','_')
            tum_bolumler=ta.bolumler(i[1])
            break
    sonux = []
    for i in tum_bolumler:
        sonux.append({'name':i[0]})
    return sonux

anime_s = [
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

while True:
    aksiyon = prompt([{
            'type': 'list',
            'name': 'aksiyon',
            'message': 'İşlemi seç',
            'choices': [
                'Anime izle',
                'Anime indir',
                'Ayarlar',
                'Yardım',
                'Kapat']
            }])['aksiyon']

    if aksiyon=='Ayarlar':
        from easygui import diropenbox
        def kaydet(n,m,v):
            if not path.isfile('ayarlar.conf'):
                with open('ayarlar.conf','w') as f:
                    lines = ['#\n','#\n','#\n']
                    lines[n] = 'global '+m+';'+m+'='+v+'\n'
                    f.writelines(lines)
            else:
                with open('ayarlar.conf','r') as f: 
                    lines=f.readlines()
                    lines[n] = 'global '+m+';'+m+'='+v+'\n'
                with open('ayarlar.conf','w') as f:
                    f.writelines(lines)

        while True:
            ayarlar_li = ['İndirilenler klasörünü seç',
                          'Yığın indirme çözünürlüğü seç',
                          'İzlerken kaydetme modu: '+str(bool(mpv_mod)),
                          'Geri dön']
            opsiyon = prompt([{
                'type': 'list',
                'name': '_',
                'message': 'İşlemi seç',
                'choices': ayarlar_li
                }])['_']
            if opsiyon is ayarlar_li[0]:
#                global debug
                oto_dizin = diropenbox()
                print('Başarılı.')
                kaydet(0,'oto_dizin','r"'+oto_dizin+'"')
            elif opsiyon is ayarlar_li[1]:
                cevap = prompt([{
                'type': 'list',
                'name': '_',
                'message': 'Çözünürlük seçin ',
                'choices': ['360p','480p','720p','En iyi']
                }])['_']
                oto_cozunurluk = rezs[rezs.index(cevap)+1]
                print('Başarılı.')
                kaydet(1,'oto_cozunurluk','"'+oto_cozunurluk+'"')
            elif opsiyon is ayarlar_li[2]:
                mpv_mod = abs(mpv_mod-1)
                kaydet(2,'mpv_mod',str(mpv_mod))
            else:
                break
    
    elif aksiyon.__contains__('Anime'):
        anime_c = prompt([
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
        }])
        hedefler = []
        prefix_hedefler = 'https://turkanime.tv/video/'
        for i in tum_bolumler:
            if anime_c['bolum'].__contains__(i[0]):
                hedefler.append([i[0],prefix_hedefler+i[1]])
        ppprint(" ")
        
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
                        if not(err):
                            print("Lütfen farklı bir alternatif seçin")
                            continue # Eğer error aldıysak kullanıcıya farklı bi alternatif için şans ver
                        flag = True
                        break
            if hedef != hedefler[-1]:
                ppprint("Sıradaki bölüme geçiliyor..")

    elif aksiyon is 'Yardım':
        from webbrowser import open as tex
        print("Yardım sayfası açılıyor..")
        tex("klavuz.html")
    elif aksiyon is 'Kapat':break
