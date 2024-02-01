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
__version__ = "8.2.2"
__build__ = "source" # source,exe,pip

def guncel_surum():
    """ En güncel sürümün numarasını "X.Y.Z" formatında edin. """
    if __build__ == "pip":
        url = "https://pypi.org/pypi/turkanime-cli/json"
        pypi = requests.get(url,timeout=5).json()
        recent_version = list(pypi['releases'].keys())[-1]
    elif __build__ == "exe":
        url = "https://api.github.com/repos/Kebablord/turkanime-indirici/releases/latest"
        release = requests.get(url,timeout=5).json()
        recent_version = release['tag_name'].replace("v","").replace("V","")
    else: # source
        url = "https://raw.githubusercontent.com/KebabLord/turkanime-indirici/master/pyproject.toml"
        source = requests.get(url,timeout=5).text
        raw = re.findall("version *= *['\"](.*?)['\"]",source)
        recent_version = raw[0] if raw else None
    return recent_version

def update_type(surum):
    """ __version__ değeri ile verilen sürümü karşılaştır, güncelliği belirle. """
    cv = __version__.split(".")
    rv = surum.split(".")
    is_guncel, utype = True, None
    for i in range(3):
        if cv[i] == rv[i]:
            continue
        if int(cv[i]) < int(rv[i]):
            is_guncel = False
            break
        break
    if not is_guncel:
        if i == 0:
            utype = "Radikal"
        elif i == 1:
            utype = "Özellik"
        else:
            utype = "Onarım"
    return utype
