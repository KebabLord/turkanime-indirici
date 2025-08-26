@echo off
setlocal ENABLEDELAYEDEXPANSION
if not exist dist (
  echo dist klasoru bulunamadi
  exit /b 1
)
for %%F in (dist\*.exe) do (
  certutil -hashfile "%%F" MD5 > "%%F.md5"
  echo MD5: %%F.md5
)
for %%F in (dist\*.zip) do (
  certutil -hashfile "%%F" MD5 > "%%F.md5"
  echo MD5: %%F.md5
)
echo Tamamlandi.
endlocal
