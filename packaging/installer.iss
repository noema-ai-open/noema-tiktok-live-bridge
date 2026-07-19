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
OutputBaseFilename=NOEMA-TikTok-Bridge-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Files]
Source: "..\dist\noema-tiktok-bridge\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\NOEMA TikTok Live Bridge"; Filename: "{app}\noema-tiktok-bridge.exe"
Name: "{autodesktop}\NOEMA TikTok Live Bridge"; Filename: "{app}\noema-tiktok-bridge.exe"

[Run]
Filename: "{app}\noema-tiktok-bridge.exe"; Description: "Bridge jetzt starten"; Flags: nowait postinstall skipifsilent
