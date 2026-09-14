; =====================================================================
; Script Inno Setup pour IPTV Hub
; =====================================================================

#define MyAppName "IPTV Hub"
#ifndef MyAppVersion
#define MyAppVersion "2.1.4"
#endif
#define MyAppPublisher "IPTV Hub Team"
#define MyAppExeName "IPTV_Hub.exe"

[Setup]
; Identifiant unique de l'application (généré pour IPTV Hub)
AppId={{D3F1E78B-5C42-4A8E-9B21-7A3B4D8E9F01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Permet une installation par utilisateur ou pour tous les utilisateurs
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=dist_installer
OutputBaseFilename=IPTV_Hub_Setup
SetupIconFile=assets\logo.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Copie l'intégralité du dossier dist/IPTV_Hub généré par PyInstaller
Source: "dist\IPTV_Hub\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
