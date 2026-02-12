; Ankismart 安装程序脚本
; 使用 Inno Setup 编译

#define MyAppName "Ankismart"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Ankismart Team"
#define MyAppURL "https://github.com/yourusername/ankismart"
#define MyAppExeName "Ankismart.exe"

[Setup]
; 应用基本信息
AppId={{A5B3C2D1-E4F5-6789-ABCD-EF0123456789}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=LICENSE
OutputDir=dist\installer
OutputBaseFilename=Ankismart-Setup-{#MyAppVersion}
SetupIconFile=src\ankismart\ui\assets\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\Ankismart\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Ankismart\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 注意: 不要在任何共享系统文件上使用 "Flags: ignoreversion"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  AppDataDir: String;
begin
  if CurStep = ssPostInstall then
  begin
    // 创建用户数据目录
    AppDataDir := ExpandConstant('{localappdata}\ankismart');
    if not DirExists(AppDataDir) then
      CreateDir(AppDataDir);

    // 创建子目录
    CreateDir(AppDataDir + '\config');
    CreateDir(AppDataDir + '\data');
    CreateDir(AppDataDir + '\logs');
    CreateDir(AppDataDir + '\cache');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDataDir: String;
  ResultCode: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppDataDir := ExpandConstant('{localappdata}\ankismart');

    // 询问是否删除用户数据
    if MsgBox('是否删除所有配置和数据文件？' + #13#10 +
              'Do you want to delete all configuration and data files?' + #13#10 + #13#10 +
              AppDataDir,
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      DelTree(AppDataDir, True, True, True);
    end;
  end;
end;
