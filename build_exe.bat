@echo off
title Compilation de IPTV Hub
cd /d "%~dp0"

echo ========================================================
echo         Compilation de l'executable IPTV Hub...
echo ========================================================

pyinstaller build.spec --clean -y

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo  Compilation reussie !
    echo  Executable disponible dans : dist\IPTV_Hub\IPTV_Hub.exe
    echo ========================================================
) else (
    echo.
    echo Une erreur est survenue lors de la compilation.
)

pause
