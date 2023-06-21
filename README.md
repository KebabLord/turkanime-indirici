# TürkAnimu-Cli
[![GitHub all releases](https://img.shields.io/github/downloads/kebablord/turkanime-indirici/total?style=flat-square)](https://github.com/KebabLord/turkanime-indirici/releases/latest)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/kebablord/turkanime-indirici?style=flat-square)](https://github.com/kebablord/turkanime-indirici/releases/latest/download/turkanimu.exe)

[![Downloads](https://static.pepy.tech/personalized-badge/turkanime-cli?period=total&units=international_system&left_color=grey&right_color=orange&left_text=Pip%20Installs)](https://pepy.tech/project/turkanime-cli)
[![Pypi version](https://img.shields.io/pypi/v/turkanime-cli?style=flat-square)](https://pypi.org/project/turkanime-cli/)

Türkanime için terminal video oynatıcı ve indirici. İtinayla her bölümü indirir & oynatır.
 - Yığın bölüm indirebilir
 - Animu izleyebilir
 - Uygulama içinden arama yapabilir
 - Fansub seçtirebilir
 - Bir yandan izlerken bir yandan animeyi kaydedebilir
 - İndirmelere kaldığı yerden devam edebilir
 
#### Desteklenen kaynaklar:
```Sibnet, Odnoklassinki, Sendvid, Mail.ru, VK, Google+, Myvi, GoogleDrive, Yandisk, Vidmoly, Yourupload, Dailymotion```

#### Yenilikler:
 - Seçim ekranı en son seçilen bölümden başlıyor, https://github.com/KebabLord/turkanime-indirici/discussions/35 https://github.com/KebabLord/turkanime-indirici/discussions/30
 - Aynı anda birden fazla bölüm indirme özelliği https://github.com/KebabLord/turkanime-indirici/pull/49
 - Önceden indirilen veya izlenen animelere izlendi ikonu seçeneği
 - Gereksinimleri uygulama içinden otomatik indirme



# Kurulum
Önceden derlenmiş sürümleri [indirebilir](https://github.com/KebabLord/turkanime-indirici/releases/latest) ya da pip ile kolayca `pip install turkanime-cli` kurabilirsiniz. Pip ile kuruyorsanız, ya da scripti kaynak kodundan çalıştırıyorsanız mpv ve geckodriver'ın sisteminizde kurulu olduğundan ve sistem path'ında olduğundan emin olun. Konuya ilişkin rehber için [wiki sayfası](https://github.com/KebabLord/turkanime-indirici/wiki/Herhangi-bir-uygulamay%C4%B1-system-path'%C4%B1na-ekleme).

 ### İzleme ekranı
 ![indirme.gif](docs/ss_izle.gif)

 ### İndirme ekranı
 ![indirme.gif](docs/ss_indir.gif)

### Yapılacaklar:
 - [ ] İndirme bitimi aksiyonları: bildirim veya bilgisayar kapatma.
 - [ ] Maximum çözünürlüğe ulaş.
 - [ ] Gui versiyon
 - [ ] Youtube-dl yerine yt-dlp'ye geçilmeli.
 - [ ] Selenium'dan kurtulma
 - [x] ~~Yeni sürüm var mı uygulama açılışında kontrol et.~~
 - [x] ~~Paralel anime indirme özelliği.~~
 - [x] ~~Progress yaratılma satırı minimal bir class ile kısaltılacak.~~
 - [x] ~~Domain güncellemesinden beridir kod stabil çalışmıyor, düzeltilecek.~~
 - [x] ~~Kod çorba gibi, basitleştirilecek.~~
 - [x] ~~Navigasyon ve indirme algoritması http talepleriyle sağlanacak.~~
 - [x] ~~Zaman bloğu olarak sleep'den kurtulunacak, elementin yüklenmesi beklenecek.~~
 - [x] ~~Prompt kütüphanesi olarak berbat durumda olan PyInquirer'den Questionary'e geçilecek.~~
 - [x] ~~Arama sonuçları da http talepleriyle getirilecek.~~
 - [x] ~~Fansub seçme özelliği tekrar eklenecek.~~
