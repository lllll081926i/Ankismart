; Ankismart installer script (Inno Setup 6)

#ifndef MyAppVersion
  #define MyAppVersion "0.1.4"
#endif

#ifndef ProjectRoot
  #define ProjectRoot ".."
#endif

#ifndef SourceDir
  #define SourceDir "{#ProjectRoot}\dist\release\app"
#endif

#ifndef OutputDir
  #define OutputDir "{#ProjectRoot}\dist\release\installer"
#endif

#define MyAppName "Ankismart"
#define MyAppPublisher "Ankismart Team"
#define MyAppURL "https://github.com/lllll081926i/Ankismart"
#define MyAppExeName "Ankismart.exe"

[Setup]
AppId={{A5B3C2D1-E4F5-6789-ABCD-EF0123456789}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir={#OutputDir}
OutputBaseFilename=Ankismart-Setup-{#MyAppVersion}
SetupIconFile={#ProjectRoot}\src\ankismart\ui\assets\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Default.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
chinesesimplified.CreateDesktopShortcutOnFinish=创建桌面快捷方式
english.CreateDesktopShortcutOnFinish=Create desktop shortcut

[Files]
Source: "{#SourceDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "model\*,models\*,.paddleocr\*,paddleocr_models\*,ocr_models\*,paddle\*,paddleocr\*,paddlex\*,cv2\*,*paddle*.dist-info\*"

[Dirs]
Name: "{app}\config"
Name: "{app}\data"
Name: "{app}\logs"
Name: "{app}\cache"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopShortcutOnFinish}"; Flags: unchecked

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
