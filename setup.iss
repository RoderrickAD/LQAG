; SKRIPT FÜR GITHUB ACTIONS (Relative Pfade)
#define MyAppName "LQAG Vorleser"
#define MyAppVersion "1.0"
#define MyAppPublisher "DeinName"
#define MyAppExeName "start_lqag.bat"

[Setup]
; WICHTIG: Erzeuge hier online eine neue UUID und ersetze sie: https://www.uuidgenerator.net/
AppId={{GENERIERE-EINE-UUID-UND-FUEGE-SIE-HIER-EIN}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputBaseFilename=LQAG_Installer
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; Das Ausgabeverzeichnis für den fertigen Installer
OutputDir=Output

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Source: "..." bezieht sich jetzt auf den Ordner, in dem diese .iss Datei liegt
Source: "start_lqag.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "src\*"; DestDir: "{app}\src"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "resources\*"; DestDir: "{app}\resources"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: shellexec postinstall skipifsilent
