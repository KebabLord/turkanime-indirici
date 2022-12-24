;; Windows için PyInstaller ile build: terminal tabanlı tek dosya exe
cd ..
pyinstaller --noconfirm --onefile --console --icon "docs\TurkAnimu.ico" --name "TurkAnimu" "turkanime.py"
