@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python Launcher was not found.
    echo Install Python 3.12 or newer from https://www.python.org/downloads/windows/
    echo Enable the option to add Python to PATH, then run this file again.
    pause
    exit /b 1
)

if not exist ".venv-build\Scripts\python.exe" (
    py -3 -m venv .venv-build
    if errorlevel 1 goto :error
)

call ".venv-build\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 goto :error
call ".venv-build\Scripts\python.exe" -m unittest discover -v
if errorlevel 1 goto :error
call ".venv-build\Scripts\python.exe" -m PyInstaller --noconfirm --windowed --onefile --name MineOrganizer --icon MOrg.ico --add-data "MOrg.ico;." --add-data "docs;docs" main.py
if errorlevel 1 goto :error

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 7\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo Inno Setup 6 or 7 was not found.
    echo Install it from https://jrsoftware.org/isinfo.php and run this file again.
    pause
    exit /b 1
)

call "%ISCC%" "installer\MineOrganizer.iss"
if errorlevel 1 goto :error

echo.
echo Build complete: dist\MineOrganizer.exe
echo Installer complete: installer\output\MineOrganizer-Setup.exe
echo Python and application dependencies are included in the executable.
echo Share only dist\MineOrganizer.exe with testers.
pause
exit /b 0

:error
echo.
echo Build failed. Read the error messages above.
pause
exit /b 1
