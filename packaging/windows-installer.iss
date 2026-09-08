#define AppName "IC2V"
#define AppVersion GetEnv("IC2V_VERSION")
#if AppVersion == ""
  #define AppVersion "0.1.0"
#endif
#define SourceDir "..\dist\IC2V"

[Setup]
AppId={{7A850668-3249-4A47-9857-9828507CFE01}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\IC2V
DefaultGroupName=IC2V
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=IC2V-{#AppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\IC2V.exe
CloseApplications=yes

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "startupicon"; Description: "Start in System Tray when Windows starts"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Icons]
Name: "{group}\IC2V"; Filename: "{app}\IC2V.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\IC2V"; Filename: "{app}\IC2V.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Windows\SendTo\IC2V"; Filename: "{app}\IC2V.exe"; WorkingDir: "{app}"
Name: "{userstartup}\IC2V"; Filename: "{app}\IC2V.exe"; Parameters: "--tray"; WorkingDir: "{app}"; Tasks: startupicon

[Run]
Filename: "{app}\IC2V.exe"; Description: "Launch IC2V"; Flags: nowait postinstall skipifsilent
