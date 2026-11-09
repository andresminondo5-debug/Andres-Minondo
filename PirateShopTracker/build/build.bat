@echo off
rem ============================================================================
rem  Pirate Shop Chest Tracker PRO - one-click build for Windows 10/11
rem  1. Installs the Python libraries (Python 3.10+ must be installed once).
rem  2. Runs the unit tests.
rem  3. Packs the app into dist\PirateShopTracker\PirateShopTracker.exe (PyInstaller).
rem  4. If Inno Setup 6 is installed, builds installer_output\PirateShopTrackerSetup.exe.
rem ============================================================================
setlocal
cd /d "%~dp0\.."

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Install it from https://www.python.org/downloads/
    echo         and tick "Add python.exe to PATH" during setup, then run this again.
    pause
    exit /b 1
)

echo.
echo [1/4] Installing libraries...
python -m pip install --upgrade pip || goto :fail
python -m pip install -r requirements.txt pyinstaller || goto :fail

echo.
echo [2/4] Running tests...
python -m unittest discover -s tests || goto :fail

echo.
echo [3/4] Building the app (PyInstaller)...
python -m PyInstaller --noconfirm --clean --windowed --name PirateShopTracker ^
    --collect-all PySide6 --collect-submodules app run_app.py || goto :fail

echo.
echo [4/4] Building the installer (Inno Setup)...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" (
    echo [INFO] Inno Setup 6 is not installed. The app is ready in dist\PirateShopTracker\
    echo        To make the installer: install Inno Setup 6 from https://jrsoftware.org/isdl.php
    echo        and run this script again.
    pause
    exit /b 0
)
"%ISCC%" build\installer.iss || goto :fail

echo.
echo DONE. Installer: %cd%\installer_output\PirateShopTrackerSetup.exe
pause
exit /b 0

:fail
echo.
echo [ERROR] The build stopped. Read the message above, fix it, and run build.bat again.
pause
exit /b 1
