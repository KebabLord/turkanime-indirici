""" TürkAnimu Downloader """
from os import environ,name
from time import sleep
import sys
import atexit
import concurrent.futures as cf
from rich import print as rprint
from rich.table import Table
from rich.live import Live
import questionary as qa
from easygui import diropenbox

from ..bypass import fetch
from ..objects import Anime, Bolum
from .dosyalar import Dosyalar
from .gereksinimler import gereksinim_kontrol_cli
from .cli_tools import prompt_tema,clear,indirme_task_cli,VidSearchCLI,CliStatus
from .version import guncel_surum, update_type

# Uygulama dizinini sistem PATH'ına ekle.
SEP = ";" if name=="nt" else ":"
environ["PATH"] +=  SEP + Dosyalar().ta_path + SEP


def eps_to_choices(liste,mark_type):
    """ - [Bolum,] listesini `questionary.Choice` listesine dönüştürür.
        - Ayrıca geçmiş.json'daki izlenen/indirilen bölümlere işaret koyar.
    """
    assert len(liste) != 0 and isinstance(liste[0], Bolum)
    slug = liste[0].anime.slug
    recent, choices, gecmis = None, [], []
    gecmis_ = Dosyalar().gecmis
    if slug in gecmis_[mark_type]:
        gecmis = gecmis_[mark_type][slug]
        recent = gecmis[-1]
    for bolum in liste:
        isim = str(bolum.title)
        if bolum.slug in gecmis:
            isim += " ●"
        choice = qa.Choice(isim,bolum)
        if bolum.slug == recent:
            recent = choice
        choices.append(choice)
    return choices, recent


def menu_loop():
    """ Ana menü interaktif navigasyonu """
    while True:
        clear()
        islem = qa.select(
            "İşlemi seç",
            choices=['Anime izle',
                    'Anime indir',
                    'Ayarlar',
                    'Kapat'],
            style=prompt_tema,
            instruction=" "
        ).ask()
        if not islem:
            break
        # Anime izle veya indir seçildiyse.
        if "Anime" in islem:
            # Seriyi seç.
            try:
                with CliStatus("Anime listesi getiriliyor.."):
                    animeler = Anime.get_anime_listesi()
                seri_ismi = qa.autocomplete(
                    'Animeyi yazın',
                    choices = [n for s,n in animeler],
                    style = prompt_tema
                ).ask()
                if seri_ismi is None:
                    continue
                seri_slug = [s for s,n in animeler if n==seri_ismi][0]
                anime = Anime(seri_slug)
            except (KeyError,IndexError):
                rprint("[red][strong]Aradığınız anime bulunamadı.[/strong][red]")
                sleep(1.5)
                continue

            while True:
                dosya = Dosyalar()
                if "izle" in islem:
                    with CliStatus("Bölümler getiriliyor.."):
                        choices, recent = eps_to_choices(anime.bolumler, mark_type="izlendi")
                    bolum = qa.select(
                        message='Bölüm seç',
                        choices=choices,
                        style=prompt_tema,
                        default=recent
                    ).ask(kbi_msg="")
                    if not bolum:
                        break
                    fansubs, sub = bolum.fansubs, None
                    if dosya.ayarlar["manuel fansub"] and len(fansubs) > 1:
                        sub = qa.select(
                            message='Fansub seç',
                            choices= fansubs,
                            style=prompt_tema,
                        ).ask(kbi_msg="")
                        if not sub:
                            break
                    # En iyi videoyu bul ve oynat, 3 şansı var.
                    success = False
                    for _ in range(3):
                        vid_cli = VidSearchCLI()
                        with vid_cli.progress:
                            best_video = bolum.best_video(
                                by_res=dosya.ayarlar["max resolution"],
                                by_fansub=sub,
                                callback=vid_cli.callback)
                        if not best_video:
                            break
                        print("  Video başlatılacak..")
                        proc = best_video.oynat(dakika_hatirla=dosya.ayarlar["dakika hatirla"])
                        if proc.returncode == 0:
                            success = True
                            break
                        best_video.is_working = False
                        print("  Video çalışmadı, başka bir video denenecek..")
                    if success:
                        dosya.set_gecmis(anime.slug, bolum.slug, "izlendi")
                else:
                    choices, recent = eps_to_choices(anime.bolumler, mark_type="indirildi")
                    bolumler = qa.checkbox(
                        message = "Bölüm seç",
                        choices=choices,
                        style=prompt_tema,
                        initial_choice=recent
                    ).ask(kbi_msg="")
                    if not bolumler:
                        break

                    # İndirme tablosu yarat ve başlat.
                    table = Table.grid(expand=False)
                    with Live(table, refresh_per_second=10, vertical_overflow="visible"):
                        futures = []
                        paralel = dosya.ayarlar.get("paralel indirme sayisi")
                        with cf.ThreadPoolExecutor(max_workers=paralel) as executor:
                            for bolum in bolumler:
                                futures.append(executor.submit(
                                    indirme_task_cli, bolum, table, dosya))
                            cf.wait(futures)

        elif islem == "Ayarlar":
            while True:
                clear()
                dosyalar = Dosyalar()
                ayarlar = dosyalar.ayarlar
                tr = lambda opt: "AÇIK" if opt else "KAPALI" # Bool to Türkçe
                ayarlar_options = [
                    'İndirilenler klasörünü seç',
                    'İzlerken kaydet: '+tr(ayarlar['izlerken kaydet']),
                    'Manuel fansub seç: '+tr(ayarlar['manuel fansub']),
                    'İzlendi/İndirildi ikonu: '+tr(ayarlar["izlendi ikonu"]),
                    'Paralel indirme sayisi: '+str(ayarlar["paralel indirme sayisi"]),
                    'Maksimum çözünürlüğe ulaş: '+tr(ayarlar["max resolution"]),
                    'Kaldığın dakikayı hatirla: '+tr(ayarlar["dakika hatirla"]),
                    'Aria2c ile hızlandır (deneysel): '+tr(ayarlar["aria2c kullan"]),
                    'Geri dön'
                ]
                ayar_islem = qa.select(
                    'İşlemi seç',
                    ayarlar_options,
                    style=prompt_tema,
                    instruction=" "
                    ).ask()

                if ayar_islem == ayarlar_options[0]:
                    indirilenler_dizin=diropenbox()
                    if indirilenler_dizin:
                        dosyalar.set_ayar("indirilenler",indirilenler_dizin)
                elif ayar_islem == ayarlar_options[1]:
                    dosyalar.set_ayar("izlerken kaydet", not ayarlar['izlerken kaydet'])
                elif ayar_islem == ayarlar_options[2]:
                    dosyalar.set_ayar('manuel fansub', not ayarlar['manuel fansub'])
                elif ayar_islem == ayarlar_options[3]:
                    dosyalar.set_ayar('izlendi ikonu', not ayarlar['izlendi ikonu'])
                elif ayar_islem == ayarlar_options[4]:
                    max_dl = qa.text(
                        message = 'Maksimum eş zamanlı kaç bölüm indirilsin?',
                        default = str(ayarlar["paralel indirme sayisi"]),
                        style = prompt_tema
                    ).ask(kbi_msg="")
                    if isinstance(max_dl,str) and max_dl.isdigit():
                        dosyalar.set_ayar("paralel indirme sayisi", int(max_dl))
                elif ayar_islem == ayarlar_options[5]:
                    dosyalar.set_ayar('max resolution', not ayarlar['max resolution'])
                elif ayar_islem == ayarlar_options[6]:
                    dosyalar.set_ayar('dakika hatirla', not ayarlar['dakika hatirla'])
                elif ayar_islem == ayarlar_options[7]:
                    dosyalar.set_ayar('aria2c kullan', not ayarlar['aria2c kullan'])
                else:
                    break

        elif islem == "Kapat":
            break


def main():
    # Güncelleme kontrolü
    try:
        with CliStatus("Güncelleme kontrol ediliyor.."):
            surum = guncel_surum()
        tip = update_type(surum)
        if tip:
            rprint(f"[yellow]{tip} Güncellemesi mevcut!! v{surum}[/yellow]")
            rprint("[yellow]Yeni özellikler için uygulamayı güncelleyebilirsiniz! [/yellow]")
            sleep(5)
    except:
        rprint("[red][strong]Güncelleme kontrol edilemedi.[/strong][red]")
        sleep(3)


    # Gereksinimleri kontrol et
    gereksinim_kontrol_cli()

    # Script herhangi bir sebepten dolayı sonlandırıldığında.
    def kapat():
        with CliStatus("Kapatılıyor.."):
            sleep(1.5) # Şimdilik placeholder
    atexit.register(kapat)

    # Türkanime'ye bağlan.
    try:
        with CliStatus("Türkanime'ye bağlanılıyor.."):
            res = fetch(None)
        if res != "200":
            raise ConnectionError
    except (ConnectionError):
        rprint("[red][strong]TürkAnime'ye ulaşılamıyor.[/strong][red]")
        sys.exit(1)

    # Navigasyon menüsünü başlat.
    clear()
    rprint("[green]!)[/green] Üst menülere dönmek için Ctrl+C kullanabilirsiniz.\n")
    sleep(1.7)
    menu_loop()


if __name__ == '__main__':
    main()
