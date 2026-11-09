; Inno Setup 6 script: builds installer_output\PirateShopTrackerSetup.exe
; Installs per user (no admin needed), creates a desktop shortcut and a Start menu entry.

#define AppName "Pirate Shop Chest Tracker PRO"
#define AppExe "PirateShopTracker.exe"
#define AppVersion "1.0.0"

[Setup]
AppId={{6F1B2C7E-3D4A-4B8E-9C11-PIRATESHOP01}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Andres Minondo
DefaultDirName={localappdata}\Programs\PirateShopTracker
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\installer_output
OutputBaseFilename=PirateShopTrackerSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: checkedonce

[Files]
Source: "..\dist\PirateShopTracker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir {#AppName} ahora"; Flags: nowait postinstall skipifsilent
