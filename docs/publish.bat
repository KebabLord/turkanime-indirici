@echo off
echo.
echo ========================================
echo  TurkAnime Downloader PyPI Publisher
echo ========================================
echo.

echo Checking for twine...
python -m pip show twine > nul 2>&1
if %errorlevel% neq 0 (
    echo twine not found. Installing...
    python -m pip install twine
) else (
    echo twine is already installed.
)

echo.
echo Cleaning up old build directories...
if exist "dist" (
    echo Removing dist directory...
    rmdir /s /q dist
)
if exist "build" (
    echo Removing build directory...
    rmdir /s /q build
)
echo Cleanup complete.
echo.

echo Building the project using Poetry...
poetry build
if %errorlevel% neq 0 (
    echo.
    echo  !!!!!!!!!!!!!!!!!!!!!!!!
    echo   Poetry build failed.
    echo  !!!!!!!!!!!!!!!!!!!!!!!!
    echo.
    pause
    exit /b %errorlevel%
)
echo Build successful.
echo.

echo Uploading packages to PyPI...
python -m twine upload dist/*
if %errorlevel% neq 0 (
    echo.
    echo  !!!!!!!!!!!!!!!!!!!!!!!!
    echo   Upload failed.
    echo  !!!!!!!!!!!!!!!!!!!!!!!!
    echo.
    pause
    exit /b %errorlevel%
)

echo.
echo ========================================
echo  Successfully published to PyPI!
echo ========================================
echo.
pause
