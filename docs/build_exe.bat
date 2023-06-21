:: Windows için PyInstaller ile build: terminal tabanlı tek dosya exe
:: Script'i bu dizinden çalıştırdığınızı varsayıyorum
@echo off
chcp 65001 >NUL

findstr /R /C:"__build__ = .exe." ..\turkanime_api\version.py>NUL || (
	echo Derlemeden önce versiyon dosyasındaki build değişkenini exe olarak değiştirmelisin
	goto :EOF
)

echo Herşeyin güncel olduğundan emin olunuyor..
pip install -U pyinstaller 1>NUL
pip install pyinstaller_versionfile 1>NUL
pip install -r ..\requirements.txt 1>NUL

echo Sürüm dosyası yaratılıyor..
(
    echo import pyinstaller_versionfile
    echo from turkanime_api.version import __version__
    echo.
    echo pyinstaller_versionfile.create_versionfile^(
    echo     output_file="versionfile.txt",
    echo     version=__version__,
    echo     company_name="TurkAnimu Dev",
    echo     file_description="Anime İndirici & Oynatıcı",
    echo     internal_name="TurkAnimu",
    echo     legal_copyright="© KebabLord, All rights reserved.",
    echo     original_filename="TurkAnimu.exe",
    echo     product_name="TurkAnimu İndirici"
    echo ^)
) > ..\version_generator.py
cd ..
py version_generator.py

echo EXE derleniyor..
pyinstaller --noconfirm --onefile --console --icon "docs\TurkAnimu.ico" --name "TurkAnimu" --version-file versionfile.txt "turkanime.py" && (
  echo Herşey yolunda gitti, çalıştırılabilir dosya: dist/TurkAnimu.exe
)

echo.
echo (KAPATMAK İÇİN ENTER'A BASIN)
set /p input=
