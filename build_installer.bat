@echo off
title Creation de l'installateur IPTV Hub
cd /d "%~dp0"

echo ========================================================
echo   Etape 1/2 : Compilation de l'executable (PyInstaller)
echo ========================================================
pyinstaller build.spec --noconfirm

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Erreur lors de la compilation PyInstaller.
    pause
    exit /b %ERRORLEVEL%
)

:: Copie de securite des dependances systeme a la racine du dossier distribuable
copy /y "lib\vulkan-1.dll" "dist\IPTV_Hub\vulkan-1.dll" >nul 2>&1
copy /y "lib\msvcp140.dll" "dist\IPTV_Hub\msvcp140.dll" >nul 2>&1
copy /y "lib\msvcp140_1.dll" "dist\IPTV_Hub\msvcp140_1.dll" >nul 2>&1
copy /y "lib\msvcp140_2.dll" "dist\IPTV_Hub\msvcp140_2.dll" >nul 2>&1

echo.
echo ========================================================
echo   Etape 2/2 : Creation de l'installateur (Inno Setup)
echo ========================================================

set "PATH=%LOCALAPPDATA%\Programs\Inno Setup 7;%PATH%"
iscc installer.iss

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo  Installateur cree avec succes !
    echo  Fichier disponible : dist_installer\IPTV_Hub_Setup.exe
    echo ========================================================
) else (
    echo.
    echo Erreur lors de la creation de l'installateur Inno Setup.
)

pause
