; Installateur Windows : copie l'application et pose une icône sur le Bureau.

#define AppName "Dictée locale"
#define AppExe "DicteeLocale.exe"
#ifndef AppVersion
#define AppVersion "1.0.0"
#endif

[Setup]
AppId={{8F4C2A71-6B1E-4D58-9C3A-7E2B5D91A046}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppName}
DefaultDirName={localappdata}\Dictee locale
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=DicteeLocale-Setup
SetupIconFile=assets\dictee.ico
UninstallDisplayIcon={app}\dictee.ico
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
ShowLanguageDialog=no

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Files]
Source: "dist\DicteeLocale\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\dictee.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\dictee.ico"
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\dictee.ico"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Lancer Dictée locale"; Flags: nowait postinstall skipifsilent unchecked
