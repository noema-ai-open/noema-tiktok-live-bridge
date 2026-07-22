; Inno-Setup-Skript — wird im CI auf einem Windows-Runner mit ISCC gebaut.
#define AppName "NOEMA TikTok Live Bridge"
#define AppVersion GetEnv("APP_VERSION")
#if AppVersion == ""
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{7E1F2C7B-9B7A-4C64-9E1D-2C9D1B6A0F41}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=NOEMA
DefaultDirName={autopf}\NOEMA TikTok Live Bridge
DefaultGroupName=NOEMA
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=NOEMA-TikTok-Bridge-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
CloseApplications=yes
CloseApplicationsFilter=noema-tiktok-bridge.exe
RestartApplications=no
SetupLogging=yes
UninstallDisplayName={#AppName} v{#AppVersion}

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[InstallDelete]
; Altbestand der früheren PyInstaller-Pakete sicher entfernen.
Type: files; Name: "{app}\noema-tiktok-bridge.exe"
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\frontend"

[Files]
Source: "..\dist\noema-tiktok-bridge\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\NOEMA TikTok Live Bridge"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\runtime\scripts\windows_launcher.py"""; WorkingDir: "{app}\runtime"
Name: "{autodesktop}\NOEMA TikTok Live Bridge"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\runtime\scripts\windows_launcher.py"""; WorkingDir: "{app}\runtime"

[Run]
Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\runtime\scripts\windows_launcher.py"""; WorkingDir: "{app}\runtime"; Description: "Bridge jetzt starten"; Flags: nowait postinstall skipifsilent
