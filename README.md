# TURKANIME İNDİRİCİ
Türkanime için terminal video oynatıcı ve indirici. İtinayla her bölümü indirir & oynatır.
 - Yığın bölüm indirebilir
 - Animu izleyebilir
 - Çözünürlük seçebilir
 - Uygulama içinden arama yapabilir
 - Bir yandan izlerken bir yandan animeyi kaydedebilir
 
#### Desteklenen kaynaklar:
```Sibnet, Odnoklassinki, Openload, Umplomp, Hdvid, Sendvid, Streamango, Fembed, RapidShare, Mail.ru, VK, Google+, Myvi, Türkanime Player```

#### İndirme bölümü:
https://github.com/KebabLord/turkanime-downloader/releases/tag/v3

 ### İndirme
 ![indirme.gif](ss_indir.gif)
 
 ### İzleme
 ![indirme.gif](ss_izle.gif)

## Geliştiriciden Not
Bu projeyi aslında selenium'u tam anlamıyla kavramak için geliştirmiştim. Selenium doğası gereği oldukça hantal, hızı direk http talepleriyle çalışmakla kıyaslanamaz. Ancak Türkanime javascriptsiz çalışmayan, hatta cloudflare koruması yüzünden javascript olmadan açılmayan bir site olduğundan şimdilik tek çözüm bu gibi duruyor. Proje bir çeşit selenyum deneme tahtası olarak başladığından kod tam anlamıyla çorba. Yine de herşeye rağmen benzer projelerle ilgilenenler için videolara ulaşmak konusunda sizi aydınlatabilir.

### Yapılacaklar:
 -  ~~Domain güncellemesinden beridir kod stabil çalışmıyor, düzeltilecek.~~
 -  ~~Kod çorba gibi, basitleştirilecek.~~
 - Navigasyon  ve indirme algoritması http talepleriyle sağlanacak.
 - Zaman bloğu olarak sleep'den kurtulanacak, elementin yüklenmesi beklenecek. 
