@echo off
setlocal
echo =======================================================
echo  Creation du raccourci Bureau pour IPTV Hub
echo =======================================================

set "SCRIPT_DIR=%~dp0"
set "TARGET_EXE=%SCRIPT_DIR%dist\IPTV_Hub\IPTV_Hub.exe"
set "ICON_PATH=%SCRIPT_DIR%assets\logo.ico"
set "SHORTCUT_PATH=%USERPROFILE%\Desktop\IPTV Hub.lnk"

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = '%TARGET_EXE%'; $s.WorkingDirectory = '%SCRIPT_DIR%dist\IPTV_Hub'; $s.IconLocation = '%ICON_PATH%,0'; $s.Description = 'Lecteur IPTV Moderne'; $s.Save()"

echo Raccourci cree sur votre Bureau avec succes : "%SHORTCUT_PATH%"
echo.
echo Vous pouvez maintenant faire un clic droit sur le raccourci Bureau et choisir "Epingler a la barre des taches" !
echo =======================================================
pause
