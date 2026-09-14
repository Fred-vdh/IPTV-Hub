@echo off
title IPTV Hub
cd /d "%~dp0"

echo ========================================================
echo               Lancement de IPTV Hub...
echo ========================================================

python main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Une erreur est survenue lors de l'execution.
    pause
)
