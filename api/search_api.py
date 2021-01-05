class TurkAnime():
    def __init__(self,driver):
        self.driver=driver
    def anime_ara(self, ara):
        self.driver.get(f"https://www.turkanime.net/arama?arama={ara}")
        liste = []
        for i in self.driver.find_elements_by_css_selector(".panel-title a"):
            liste.append([i.text,i.get_attribute("href").split("anime/")[1]])
        return liste

    def bolumler(self, anime):
        self.driver.get("https://www.turkanime.net/anime/{}".format(anime))
        liste = []
        for i in self.driver.find_elements_by_css_selector(".bolumAdi"):
            sub_url = i.find_element_by_xpath("..").get_attribute("href")
            sub_url = sub_url.split("video/")[1]
            liste.append([i.text,sub_url])
        return liste