from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from time import sleep as delay
from os import system as cmd

driver = webdriver.Firefox()

hedef = "https://www.turkanime.tv/video/mushishi-zoku-shou-3-bolum" #örnek hedef
#hedef = input(r"url: ")


#LOCAL VİDEO PLAYERLARIN LİSTESİ
players_lokal= [
	"TÜRKANİME",
	"FEMBED"
]

#Popup kapatıcı
def killPopup():
	if (len(driver.window_handles)>1):
		driver.switch_to.window(driver.window_handles[1])
		driver.close()
		driver.switch_to.window(driver.window_handles[0])
		return True
	else:
		return False

def prompt_exit(url_):
	print("Video bulundu!!")
	driver.close()
	oynat = input("indir? (Y/N)")

	if (oynat=="y"):
		cmd("wget "+url_)
	else:
		cmd("mpv "+url_)
	exit()


# Büyü başlıyor :3
driver.get(hedef)


# Sayfanın yüklenmesini bekle
while True:
	try:
		assert "Bölüm" in driver.title
	except:
		continue
	finally:
		break  

# Fansubları çekti
fansublar = driver.find_elements_by_xpath("//div[@class='panel-body']/div/button")
print("Mevcut fansublar:")
for fansub in fansublar:
	print(fansub.text)

# Örnek olarak birinci fansub'a tıkladı
fansublar[1].click()
delay(2)
killPopup() # popup açıldıysa gebert

# Alternatifleri çekti
print("Mevcut alternatifler")
alternatifler = driver.find_elements_by_xpath("//div[@class='panel-body']/div[@class='btn-group']/button")
sites = []
# Alternatifler listesinde buton kodları, sites listesinde butonların isimleri var
for alternatif in alternatifler:
	sites.append(alternatif.text)
	print(alternatif.text)
killPopup()

# Rapid Video çekici
def getRapidVid():
	play_button = driver.find_element_by_xpath("//div[@class='panel-body']/div[@class='video-icerik']/iframe")
	delay(0.5)
	killPopup()
	play_button.click()
	driver.close()
	driver.switch_to.window(driver.window_handles[0])
	delay(4.5)
	raw = driver.find_element_by_id("videojs_html5_api").get_attribute("innerHTML")
	raws = raw.split('"')
	dpi480 = raws[1]
	dpi720 = raws[9]
	prompt(dpi480)

if sites.__contains__("RAPIDVIDEO"):
	alternatifler[sites.index("RAPIDVIDEO")].click()
	delay(4)
	getRapidVid()


# Local alternatif çekici
def fetFembedVid():
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

	#   Url 2 iframe katmaninin icinde sakli
		try:
			iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
			driver.switch_to.frame(iframe_1)
			iframe_2 = driver.find_element_by_css_selector("iframe")
			driver.switch_to.frame(iframe_2)
			raw = driver.find_element_by_css_selector(".jw-media").get_attribute("innerHTML")
			url = raw[raw.index("src")+5:raw.index("></")-1]
		except:
			print("Videoya erişilemiyor")
			return False
		prompt(url)

for player in players_lokal:
	if sites.__contains__(player):
		alternatifler[sites.index(player)].click()
		delay(4)
		getLokalVid()



""" quick notes
RAPIDVIDEO
id="videojs_html5_api"
https://www.turkanime.tv/video/fairy-tail-final-series-41-bolum
"""