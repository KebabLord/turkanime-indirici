from time import sleep

# POPUP PLAYERLAR
def getExternalVidOf(driver):
    """ Türkanimenin yeni sekmede açtığı playerlar """
    try:
        sleep(5)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe") #iframe'in içine gir
        driver.switch_to.frame(iframe_1)
        url = driver.find_element_by_css_selector("#link").get_attribute("href") #linki ceple
    except Exception as e: # HTML DOSYASI HATA VERİRSE
        print(e)
        return False
    else:
        return url

# TÜRKANİME PLAYER
def getTurkanimeVid(driver):
    try: # iki iframe katmanından oluşuyor
        sleep(4)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        iframe_2 = driver.find_element_by_css_selector("iframe")
        driver.switch_to.frame(iframe_2)
        url = driver.find_element_by_css_selector(".jw-media").get_attribute("src")
    except Exception as f:
        print(f)
        return False
    else:
        return url

# MAİLRU
def getMailVid(driver):
    try: # iki iframe katmanından oluşuyor
        sleep(8)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        iframe_2 = driver.find_element_by_css_selector("iframe")
        driver.switch_to.frame(iframe_2)
        url = driver.find_element_by_css_selector(".b-video-controls__mymail-link").get_attribute("href")
    except Exception as f:
        print(f)
        return False
    else:
        return url

# FEMBED
def getFembedVid(driver): #Fembed'de url'ye ulaşabilmek için iki kere tıklamak gerekiyor.
    try:
        sleep(4)
        play_button = driver.find_element_by_xpath("//div[@class='panel-body']/div[@class='video-icerik']/iframe")
        # Video url'sini ortaya çıkartmayı dene
        while True:
            play_button.click()
            sleep(2)
            killed = killPopup()
            if not killed:
                sleep(1)
                play_button.click()
                break
        #  Url 2 iframe katmaninin icinde sakli
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        iframe_2 = driver.find_element_by_css_selector("iframe")
        driver.switch_to.frame(iframe_2)
        url = driver.find_element_by_css_selector(".jw-video").get_attribute("src")
    except:
        return False
    return url

# OPENLOAD
def getOLOADVid(driver):
    sleep(3)
    driver.find_element_by_xpath("//div[@class='panel-body']/div[@class='video-icerik']/iframe").click()
    driver.switch_to.window(driver.window_handles[1])
    i = 0
    while i<7:
        sleep(1)
        try:
            driver.find_element_by_tag_name('body').click()
            sleep(2)
            while len(driver.window_handles)>2:
                driver.switch_to.window(driver.window_handles[2])
                driver.close()
            driver.switch_to.window(driver.window_handles[1])
            sleep(2.3)
            url = driver.find_elements_by_tag_name('video')[0].get_attribute('src')
        except:
            i+=1
            continue
        else:
            driver.switch_to.window(driver.window_handles[0])
            return url
    return False

# MYVI
def getMyviVid(driver):
    try:
        sleep(3.5)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        iframe_2 = driver.find_element_by_tag_name("iframe")
        driver.switch_to.frame(iframe_2)
        url = driver.find_elements_by_tag_name("link")[0].get_attribute("href")
    except Exception as f:
        print(f)
        return False
    else:
        return url

# VK
def getVKvid(driver):
    try:
        sleep(6)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        iframe_2 = driver.find_element_by_tag_name("iframe")
        driver.switch_to.frame(iframe_2)
        url = driver.find_element_by_css_selector('.videoplayer_btn_vk').get_attribute('href')
    except Exception as f:
        print(f)
        return False
    else:
        return url

# Google+
def getGPLUSvid(driver):
    try: # iki iframe katmanından oluşuyor
        sleep(4)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        iframe_2 = driver.find_element_by_css_selector("iframe")
        driver.switch_to.frame(iframe_2)
        url = driver.find_element_by_css_selector(".jw-media").get_attribute("src")
    except Exception as f:
        print(f)
        return False
    else:
        return url

# ODNOKLASSINKI
def getOKRUvid(driver):
    try: # iki iframe katmanından oluşuyor
        sleep(4)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        url=driver.find_element_by_xpath('//object/param[@name="flashvars"]').get_attribute('value')
        url="http://www.ok.ru/videoembed/"+url[url.index('mid%3D')+6:url.index('&locale=tr')]
    except Exception as f:
        print(f)
        return False
    else:
        return url

# SIBNET
def getSIBNETvid(driver):
    try: # iki iframe katmanından oluşuyor
        sleep(4)
        iframe_1 = driver.find_element_by_css_selector(".video-icerik iframe")
        driver.switch_to.frame(iframe_1)
        iframe_2 = driver.find_element_by_css_selector("iframe")
        driver.switch_to.frame(iframe_2)
        url = driver.find_elements_by_tag_name('meta')[7].get_attribute('content')
    except Exception as e:
        print(e)
        return False
    else:
        return url

players = { # Bütün desteklenen playerlar
    "SIBNET":getSIBNETvid,
    "FEMBED":getFembedVid,
    "OPENLOAD":getOLOADVid,
    "MAIL":getMailVid,
    "VK":getVKvid,
    "GPLUS":getGPLUSvid,
    "MYVI":getMyviVid,
    "TÜRKANİME":getTurkanimeVid,
    "ODNOKLASSNIKI":getOKRUvid,
    "RAPIDVIDEO":getExternalVidOf,
    "UMPLOMP":getExternalVidOf,
    "HDVID":getExternalVidOf,
    "SENDVID":getExternalVidOf,
    "STREAMANGO":getExternalVidOf
}
