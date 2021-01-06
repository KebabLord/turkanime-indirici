class TurkAnime():
    def __init__(self,driver):
        self.driver=driver
    def anime_ara(self, ara):
        self.driver.get(f"https://www.turkanime.net/arama?arama={ara}")
        if "/anime/" in self.driver.current_url:
            liste = [[self.driver.title, self.driver.current_url.split("anime/")[1]]]
            self.driver.get("about:blank")
            return liste

        liste = []
        for i in self.driver.find_elements_by_css_selector(".panel-title a"):
            liste.append([i.text,i.get_attribute("href").split("anime/")[1]])
        return liste

    def bolumler(self, anime):
        self.driver.get("https://www.turkanime.net/anime/{}".format(anime))
        liste = []
        for i in self.driver.find_elements_by_css_selector(".bolumAdi"):
            sub_element = i.find_element_by_xpath("..")
            sub_url = sub_element.get_attribute("href").split("video/")[1]
            sub_text = sub_element.get_attribute("innerText")
            liste.append([sub_text,sub_url])
        return liste