"""
Versiyon tutumu ve kontrolü modülü.
Sürüm numarası PEP8 standartınca oluşturuldu
    X.Y.Z = Major,   Minor,   Patch
            Önemli,  Özellik, Onarım

Script çok farklı şekillerde servis edildiğinden
build çeşiti ve versiyon numarası bu script'e embedlandı.
"""
import re
import requests
__author__ = "https://github.com/Kebablord/turkanime-indirici"
__version__ = "7.1.3"
__build__ = "source" # source,exe,pip

isGuncel, update_type = True, None

# Build tipine göre son sürümü edin
if __build__ == "pip":
    URL = "https://pypi.org/pypi/turkanime-cli/json"
    pypi = requests.get(URL).json()
    recent_version = list(pypi['releases'].keys())[-1]
elif __build__ == "exe":
    URL = "https://api.github.com/repos/Kebablord/turkanime-indirici/releases/latest"
    release = requests.get(URL).json()
    recent_version = release['tag_name'].replace("v","").replace("V","")
else: # source
    URL = "https://raw.githubusercontent.com/kebablord/turkanime-indirici/master/turkanime_api/version.py"
    source = requests.get(URL).text
    raw = re.findall('__version__.*?"(.*?)"',source)
    recent_version = raw[0] if raw else None

# Eğer güncelleme mevcutsa güncelleme tipini belirt
if not recent_version:
    print("Güncelleme kontrol edilemedi.")
else:
    cv = __version__.split(".")
    rv = recent_version.split(".")
    for i in range(3):
        if cv[i] == rv[i]:
            continue
        if int(cv[i]) < int(rv[i]):
            isGuncel = False
            break
        break
    if not isGuncel:
        if i == 0:
            update_type = "Radikal"
        elif i == 1:
            update_type = "Özellik"
        else:
            update_type = "Onarım"
