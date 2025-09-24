""" TürkAnimu Downloader CLI """
from os import environ, name, path
from time import sleep
import sys
import atexit
import concurrent.futures as cf
from rich import print as rprint
from rich.table import Table
from rich.live import Live
import questionary as qa
from easygui import diropenbox

# Tkinter import - cross-platform klasör seçimi için
try:
    import tkinter as tk
    from tkinter import filedialog
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False


def select_download_folder(current_path=None):
    """
    Cross-platform klasör seçme fonksiyonu.
    Tkinter'i tercih eder, fallback olarak easygui kullanır.
    """
    if TKINTER_AVAILABLE:
        try:
            # Tkinter root window oluştur (görünmez)
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)  # Windows'ta üstte tut

            # Başlangıç dizinini ayarla
            initial_dir = None
            if current_path and path.exists(path.expanduser(current_path)):
                initial_dir = path.expanduser(current_path)
            elif current_path:
                # current_path bir değişken ise onu kullan
                initial_dir = current_path

            # Klasör seçme dialog'u
            folder_path = filedialog.askdirectory(
                title="TürkAnimu - İndirme Klasörünü Seçin",
                initialdir=initial_dir,
                mustexist=True
            )

            root.destroy()

            if folder_path:  # Kullanıcı bir klasör seçti
                return folder_path

        except Exception as e:
            print(f"Tkinter dialog hatası: {e}")

    # Fallback: easygui kullan
    try:
        return diropenbox(
            msg="İndirme klasörünü seçin",
            title="TürkAnimu - İndirme Klasörü Seçimi",
            default=current_path or "~/Downloads"
        )
    except Exception as e:
        print(f"Easygui dialog hatası: {e}")
        return None

from ..bypass import fetch
from ..objects import Anime
from ..sources import search_animecix
from ..sources.animecix import CixAnime
from ..sources.adapter import AdapterAnime, AdapterBolum
from .dosyalar import Dosyalar
from .gereksinimler import gereksinim_kontrol_cli
from .cli_tools import prompt_tema, clear, indirme_task_cli, VidSearchCLI, CliStatus
from .version import guncel_surum, update_type

# Uygulama dizinini sistem PATH'ına ekle
SEP = ";" if name == "nt" else ":"
environ["PATH"] += SEP + Dosyalar().ta_path + SEP


def eps_to_choices(liste, mark_type):
    """
    Bölüm listesi -> questionary.Choice listesi, geçmiş işaretleriyle.
    """
    assert len(liste) != 0
    slug = getattr(liste[0].anime, 'slug', '')
    recent, choices, gecmis = None, [], []
    gecmis_ = Dosyalar().gecmis
    if slug in gecmis_[mark_type]:
        gecmis = gecmis_[mark_type][slug]
        recent = gecmis[-1]
    for bolum in liste:
        isim = str(bolum.title)
        if bolum.slug in gecmis:
            isim += " ●"
        choice = qa.Choice(isim, bolum)
        if bolum.slug == recent:
            recent = choice
        choices.append(choice)
    return choices, recent


def _norm_source(val: str) -> str:
    s = str(val or "").lower()
    return "animecix" if "animecix" in s else "turkanime"


def _source_title(code: str) -> str:
    return "AnimeciX (deneysel)" if _norm_source(code) == "animecix" else "TürkAnime"


def menu_loop():
    """ Ana menü interaktif navigasyonu """
    while True:
        clear()
        islem = qa.select(
            "İşlemi seç",
            choices=['Anime izle', 'Anime indir', 'Kaynak seç', 'Ayarlar', 'Kapat'],
            style=prompt_tema,
            instruction="Yukarı/Aşağı ile gezin • Enter ile onayla"
        ).ask()
        if not islem:
            break

        if "Anime" in islem:
            # Seriyi seç
            try:
                kay = _norm_source(Dosyalar().ayarlar.get("kaynak", "turkanime"))
                if kay == "animecix":
                    q = qa.text("AnimeciX: aramak için yazın", style=prompt_tema).ask(kbi_msg="")
                    if not q:
                        continue
                    with CliStatus("AnimeciX aranıyor.."):
                        found = search_animecix(q) or []
                    if not found:
                        raise KeyError
                    choices = [qa.Choice(name, (aid, name)) for (aid, name) in found]
                    pick = qa.select("Seri seç", choices=choices, style=prompt_tema,
                                      instruction="Yukarı/Aşağı • Enter").ask()
                    if not pick:
                        continue
                    seri_id, seri_ismi = pick
                    anime = None
                    seri_slug = str(seri_id)
                else:
                    with CliStatus("Anime listesi getiriliyor.."):
                        animeler = Anime.get_anime_listesi()
                    seri_ismi = qa.autocomplete(
                        'Animeyi yazın', choices=[n for s, n in animeler], style=prompt_tema
                    ).ask()
                    if seri_ismi is None:
                        continue
                    seri_slug = [s for s, n in animeler if n == seri_ismi][0]
                    anime = Anime(seri_slug)
            except (KeyError, IndexError):
                rprint("[red][strong]Aradığınız anime bulunamadı.[/strong][red]")
                sleep(1.5)
                continue

            while True:
                dosya = Dosyalar()
                if "izle" in islem:
                    with CliStatus("Bölümler getiriliyor.."):
                        if anime is None:
                            cix = CixAnime(int(seri_slug), seri_ismi)
                            eps = cix.episodes
                            an = AdapterAnime(slug=str(cix.id), title=cix.title)
                            bolumler = [AdapterBolum(e.url, e.title, an) for e in eps]
                        else:
                            bolumler = anime.bolumler
                        choices, recent = eps_to_choices(bolumler, mark_type="izlendi")
                    bolum = qa.select(
                        message='Bölüm seç', choices=choices, style=prompt_tema, default=recent,
                        instruction="Yukarı/Aşağı • Enter"
                    ).ask(kbi_msg="")
                    if not bolum:
                        break
                    fansubs, sub = getattr(bolum, 'fansubs', []), None
                    if dosya.ayarlar["manuel fansub"] and len(fansubs) > 1:
                        sub = qa.select(
                            message='Fansub seç', choices=fansubs, style=prompt_tema,
                            instruction="Yukarı/Aşağı • Enter"
                        ).ask(kbi_msg="")
                        if not sub:
                            break
                    # En iyi videoyu bul ve oynat, 3 deneme
                    success = False
                    for _ in range(3):
                        vid_cli = VidSearchCLI()
                        with vid_cli.progress:
                            best_video = bolum.best_video(
                                by_res=dosya.ayarlar["max resolution"], by_fansub=sub, callback=vid_cli.callback
                            )
                        if not best_video:
                            break
                        print("  Video başlatılacak..")
                        proc = best_video.oynat(dakika_hatirla=dosya.ayarlar["dakika hatirla"])
                        if proc.returncode == 0:
                            success = True
                            break
                        best_video.is_working = False
                        print("  Video çalışmadı, başka bir video denenecek..")
                    if success and getattr(bolum, 'anime', None):
                        dosya.set_gecmis(bolum.anime.slug, bolum.slug, "izlendi")
                else:
                    if anime is None:
                        cix = CixAnime(int(seri_slug), seri_ismi)
                        eps = cix.episodes
                        an = AdapterAnime(slug=str(cix.id), title=cix.title)
                        b_list = [AdapterBolum(e.url, e.title, an) for e in eps]
                        choices, recent = eps_to_choices(b_list, mark_type="indirildi")
                    else:
                        choices, recent = eps_to_choices(anime.bolumler, mark_type="indirildi")

                    # Büyük listelerde önce basit bir filtre soralım
                    if len(choices) > 10:
                        filt = qa.text("Bölüm ara/filtre (boş geçilebilir)", style=prompt_tema).ask(kbi_msg="")
                        if filt:
                            choices = [c for c in choices if filt.lower() in str(c.title).lower()]

                    bolumler = qa.checkbox(
                        message="Bölüm seç",
                        choices=choices,
                        style=prompt_tema,
                        initial_choice=recent,
                        instruction="Boşluk: seç • a: tümünü değiştir • i: tersine çevir • Enter: onayla"
                    ).ask(kbi_msg="")
                    if not bolumler:
                        break
                    table = Table.grid(expand=False)
                    with Live(table, refresh_per_second=10, vertical_overflow="visible"):
                        futures = []
                        paralel = dosya.ayarlar.get("paralel indirme sayisi")
                        with cf.ThreadPoolExecutor(max_workers=paralel) as executor:
                            for bolum in bolumler:
                                futures.append(executor.submit(
                                    indirme_task_cli, bolum, table, dosya
                                ))
                            cf.wait(futures)

        elif islem == "Kaynak seç":
            ds = Dosyalar()
            kay = _norm_source(ds.ayarlar.get("kaynak", "turkanime"))
            # Questionary sürümleri arasında Choice(name,value) ile default eşleşmesi sorun çıkarabiliyor.
            # Bu yüzden düz string seçenekler kullanıp başlıktan koda map ediyoruz.
            secenekler = ["TürkAnime", "AnimeciX (deneysel)"]
            varsayilan = _source_title(kay)  # "TürkAnime" veya "AnimeciX (deneysel)"
            sec_title = qa.select(
                "Kaynak seç",
                choices=secenekler,
                default=varsayilan,
                style=prompt_tema,
                instruction="Yukarı/Aşağı • Enter",
            ).ask()
            if sec_title:
                sec = _norm_source(sec_title)
                ds.set_ayar("kaynak", sec)

        elif islem == "Ayarlar":
            while True:
                clear()
                dosyalar = Dosyalar()
                ayarlar = dosyalar.ayarlar
                tr = lambda opt: "AÇIK" if opt else "KAPALI"
                ayarlar_options = [
                    'İndirilenler klasörünü seç',
                    'İzlerken kaydet: ' + tr(ayarlar['izlerken kaydet']),
                    'Manuel fansub seç: ' + tr(ayarlar['manuel fansub']),
                    'İzlendi/İndirildi ikonu: ' + tr(ayarlar["izlendi ikonu"]),
                    'Paralel indirme sayisi: ' + str(ayarlar["paralel indirme sayisi"]),
                    'Maksimum çözünürlüğe ulaş: ' + tr(ayarlar["max resolution"]),
                    'Kaldığın dakikayı hatirla: ' + tr(ayarlar["dakika hatirla"]),
                    'Aria2c ile hızlandır (deneysel): ' + tr(ayarlar["aria2c kullan"]),
                    'Geri dön'
                ]
                ayar_islem = qa.select(
                    'İşlemi seç', ayarlar_options, style=prompt_tema,
                    instruction="Yukarı/Aşağı • Enter"
                ).ask()

                if ayar_islem == ayarlar_options[0]:
                    indirilenler_dizin = select_download_folder(ayarlar.get("indirilenler"))
                    if indirilenler_dizin:
                        dosyalar.set_ayar("indirilenler", indirilenler_dizin)
                elif ayar_islem == ayarlar_options[1]:
                    dosyalar.set_ayar("izlerken kaydet", not ayarlar['izlerken kaydet'])
                elif ayar_islem == ayarlar_options[2]:
                    dosyalar.set_ayar('manuel fansub', not ayarlar['manuel fansub'])
                elif ayar_islem == ayarlar_options[3]:
                    dosyalar.set_ayar('izlendi ikonu', not ayarlar['izlendi ikonu'])
                elif ayar_islem == ayarlar_options[4]:
                    max_dl = qa.text(
                        message='Maksimum eş zamanlı kaç bölüm indirilsin?',
                        default=str(ayarlar["paralel indirme sayisi"]),
                        style=prompt_tema
                    ).ask(kbi_msg="")
                    if isinstance(max_dl, str) and max_dl.isdigit():
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
    except Exception:
        rprint("[red][strong]Güncelleme kontrol edilemedi.[/strong][red]")
        sleep(3)

    # Gereksinimleri kontrol et (embed edilmiş araçlar kullanılıyor)
    # gereksinim_kontrol_cli()

    # Script kapanışında
    def kapat():
        with CliStatus("Kapatılıyor.."):
            sleep(1.5)
    atexit.register(kapat)

    # Türkanime'ye bağlan
    try:
        with CliStatus("Türkanime'ye bağlanılıyor.."):
            _ = fetch(None)  # Create Session
    except (ConnectionError, AssertionError):
        rprint("[red][strong]TürkAnime'ye ulaşılamıyor.[/strong][red]")
        sys.exit(1)

    # Navigasyon
    clear()
    rprint("[green]!)[/green] Üst menülere dönmek için Ctrl+C kullanabilirsiniz.\n")
    sleep(1.7)
    menu_loop()


if __name__ == '__main__':
    main()
