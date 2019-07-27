# Türkanime Video Player/Downloader 1.0.0
# YAPILACAKLAR LİSTESİ
"""
- Openload alternatifi ve videoların çalışıp çalışmadığını denetleyen daha iyi bir sistem ekleyeceğim
- Animelere ve bölümlerinin -videoların değil- linklerine,ulaşabileceğimiz bir sistem, şuan benim yaptığım sistem senden direk url girmeni istiyor, biraz saçma x3
- Terminal projesi kusursuz olursa gui geliştirmek
"""

from selenium import webdriver
from time import sleep as delay
from os import system as cmd

driver = webdriver.Firefox() # sürücüyü başlat

HARICILER = [
		"HDVID",
		"RAPIDVIDEO",
		"STREAMANGO",
		"USERSCLOUD",
		"SENDVID"
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

# Url elde edildikten sonra indirici/oynatıcı
def prompt_exit(url_):
	print("Video bulundu!!")
	driver.close()
	indir = input("indir? (Y/N)")
	basariStatus = 0
	if (indir=="y"):
		basariStatus = cmd("youtube-dl -o video.mp4 "+url_)
	else:
		basariStatus = cmd("mpv "+url_)
	if (basariStatus != 0): # 404 alındıysa
		print("Bu alternatifte video bulunamadı.")
	else:
		exit()

# Fansub listeleyici
fansublar = []
def getFansublar():
	global fansublar
	fansublar = driver.find_elements_by_xpath("//div[@class='panel-body']/div/button")
	print("MEVCUT FANSUBLAR:")
	for fansub in fansublar:
		print(fansub.text)

# Video player listeleyici (fansub seçildikten sonra)
alternatifler = []
sites = []
def getAlternatifler():
	global alternatifler,sites
	print("Mevcut alternatifler")
	alternatifler = driver.find_elements_by_xpath("//div[@class='panel-body']/div[@class='btn-group']/button")
	sites.clear()
	#! "alternatifler" listesinde butonların html kodları ; "sites" listesinde butonların isimleri var
	for alternatif in alternatifler:
		sites.append(alternatif.text)
		print(alternatif.text)
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
	print("Şuan denenen alternatif: "+NYAN)
	alternatifler[sites.index(NYAN)].click() #alternatife tıkla
	delay(4)
	try:
		iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe") #iframe'in içine gir
		driver.switch_to.frame(iframe_1)
		url = driver.find_element_by_css_selector("#link").get_attribute("href") #linki ceple
	except:
		print("Videoya erişilemiyor")
		return False
	prompt_exit(url)

# TÜRKANİME PLAYER
def getTurkanimeVid(): 
	alternatifler[sites.index("TÜRKANİME")].click()
	delay(4)
	try: # iki iframe katmanından oluşuyor
		iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
		driver.switch_to.frame(iframe_1)
		iframe_2 = driver.find_element_by_css_selector("iframe")
		driver.switch_to.frame(iframe_2)
		url = driver.find_element_by_css_selector(".jw-media").get_attribute("src")
	except:
		print("Videoya erişilemiyor")
		return False
	prompt_exit(url)

# MAİLRU PLAYER
def getMailVid():
	alternatifler[sites.index("MAIL")].click()
	delay(4)
	try: # iki iframe katmanından oluşuyor
		iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
		driver.switch_to.frame(iframe_1)
		iframe_2 = driver.find_element_by_css_selector("iframe")
		driver.switch_to.frame(iframe_2)
		url = driver.find_element_by_css_selector(".b-video-controls__mymail-link").get_attribute("href")
	except:
		print("Videoya erişilemiyor")
		return False
	prompt_exit(url)

# FEMBED PLAYER
def getFembedVid(): #Fembed nazlıdır, videoya bir kere tıklanılması gerekiyor linki alabilmek için
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
	try:
		iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
		driver.switch_to.frame(iframe_1)
		iframe_2 = driver.find_element_by_css_selector("iframe")
		driver.switch_to.frame(iframe_2)
		url = driver.find_element_by_css_selector(".jw-media").get_attribute("src")
	except:
		print("Videoya erişilemiyor")
		return False
	prompt_exit(url)



## !! MANUEL DEMO !! ##

#hedef = "https://www.turkanime.tv/video/mushishi-zoku-shou-3-bolum" #örnek hedef
hedef = input("HEDEF: ")
driver.get(hedef) # bölüme git
bekleSayfaninYuklenmesini()
killPopup()

delay(3)
getFansublar() #fansubları güncelledi
fansublar[0].click() #Örnek olarak birinci fansubu seçti
delay(2)
killPopup() #popup açıldıysa gebert

getAlternatifler() #alternatifleri güncelledi
delay(2)
killPopup()

# Buradan sonra bütün alternatifleri denemeye başlıyor link elde edene kadar -link yoksa sıçtu-
for harici in HARICILER: # ilk olarak uzak alternatifler
	if sites.__contains__(harici):
		getExternalVidOf(harici)
#sonra iframe alternatifler
if sites.__contains__("TÜRKANİME"):
	getTurkanimeVid()
if sites.__contains__("FEMBED"):
	getFembedVid()
if sites.__contains__("MAIL"):
	getMailVid()