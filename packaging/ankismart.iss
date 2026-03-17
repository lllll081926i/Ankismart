; Ankismart installer script (Inno Setup 6)

#ifndef MyAppVersion
  #define MyAppVersion "1.1"
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
ShowLanguageDialog=yes
LanguageDetectionMethod=none
UsePreviousLanguage=no
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "chinesesimplified"; MessagesFile: "{#ProjectRoot}\packaging\languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
chinesesimplified.CreateDesktopShortcutOnFinish=创建桌面快捷方式
chinesesimplified.OpenInstallDirOnFinish=打开安装目录
chinesesimplified.WelcomeHeadline=安装 Ankismart
chinesesimplified.WelcomeBody=Ankismart 会把文档转换、卡片生成与推送流程集中到一个桌面工具里。安装程序将把应用文件放在当前目录，配置保存在 %LOCALAPPDATA%\\ankismart，日志保存在安装目录下的 logs 文件夹中。
chinesesimplified.SelectDirBody=请选择 Ankismart 的安装位置。程序文件会写入这里，配置仍保存在 %LOCALAPPDATA%\\ankismart，日志写入安装目录下的 logs 文件夹。
chinesesimplified.FinishedHeadline=Ankismart 已准备就绪
chinesesimplified.FinishedBody=安装已经完成。你现在可以立即启动 Ankismart，开始导入文档、生成卡片并推送到 Anki。
chinesesimplified.RemoveUserDataOnUninstall=卸载时删除此用户的配置与本地数据（%LOCALAPPDATA%\\ankismart）
english.CreateDesktopShortcutOnFinish=Create desktop shortcut
english.OpenInstallDirOnFinish=Open install directory
english.WelcomeHeadline=Install Ankismart
english.WelcomeBody=Ankismart brings document conversion, card generation, review, and Anki delivery into one desktop app. The installer keeps app files here, stores configuration in %LOCALAPPDATA%\\ankismart, and writes logs to the local logs folder beside the executable.
english.SelectDirBody=Choose where Ankismart should be installed. App files will be written here, configuration stays in %LOCALAPPDATA%\\ankismart, and logs are stored in the local logs folder beside the executable.
english.FinishedHeadline=Ankismart is ready
english.FinishedBody=Setup has finished. You can launch Ankismart now to import documents, generate cards, and send them to Anki.
english.RemoveUserDataOnUninstall=Remove this user's configuration and local data during uninstall (%LOCALAPPDATA%\\ankismart)

[Files]
Source: "{#SourceDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "model\*,models\*,.paddleocr\*,paddleocr_models\*,ocr_models\*,paddle\*,paddleocr\*,paddlex\*,cv2\*,*paddle*.dist-info\*"

[Dirs]
Name: "{app}\config"
Name: "{app}\data"
Name: "{app}\logs"
Name: "{app}\cache"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent unchecked
Filename: "{win}\explorer.exe"; Parameters: """{app}"""; Description: "{cm:OpenInstallDirOnFinish}"; Flags: nowait postinstall skipifsilent unchecked

[Code]
var
  RemoveUserDataCheck: TNewCheckBox;
  DesktopIconCheck: TNewCheckBox;

procedure ApplyWizardTypography();
begin
  WizardForm.Font.Name := 'Microsoft YaHei UI';
  WizardForm.WelcomeLabel1.Font.Name := WizardForm.Font.Name;
  WizardForm.WelcomeLabel1.Font.Style := [fsBold];
  WizardForm.WelcomeLabel1.Font.Size := 14;
  WizardForm.WelcomeLabel2.Font.Name := WizardForm.Font.Name;
  WizardForm.WelcomeLabel2.Font.Size := 9;
  WizardForm.FinishedHeadingLabel.Font.Name := WizardForm.Font.Name;
  WizardForm.FinishedHeadingLabel.Font.Style := [fsBold];
  WizardForm.FinishedHeadingLabel.Font.Size := 14;
  WizardForm.FinishedLabel.Font.Name := WizardForm.Font.Name;
  WizardForm.FinishedLabel.Font.Size := 9;
  WizardForm.SelectDirLabel.Font.Name := WizardForm.Font.Name;
  WizardForm.SelectDirLabel.Font.Size := 9;
  WizardForm.DirEdit.Font.Name := WizardForm.Font.Name;
  WizardForm.DirEdit.Font.Size := 9;
end;

procedure ApplyWizardCopy();
begin
  WizardForm.WelcomeLabel1.Caption := ExpandConstant('{cm:WelcomeHeadline}');
  WizardForm.WelcomeLabel2.Caption := ExpandConstant('{cm:WelcomeBody}');
  WizardForm.SelectDirLabel.Caption := ExpandConstant('{cm:SelectDirBody}');
  WizardForm.FinishedHeadingLabel.Caption := ExpandConstant('{cm:FinishedHeadline}');
  WizardForm.FinishedLabel.Caption := ExpandConstant('{cm:FinishedBody}');
end;

procedure InitializeWizard();
begin
  ApplyWizardTypography();
  ApplyWizardCopy();

  DesktopIconCheck := TNewCheckBox.Create(WizardForm.FinishedPage);
  DesktopIconCheck.Parent := WizardForm.FinishedPage;
  DesktopIconCheck.Left := WizardForm.RunList.Left;
  DesktopIconCheck.Top := WizardForm.RunList.Top;
  DesktopIconCheck.Width := WizardForm.RunList.Width;
  DesktopIconCheck.Caption := ExpandConstant('{cm:CreateDesktopShortcutOnFinish}');
  DesktopIconCheck.Checked := True;

  WizardForm.RunList.Top := DesktopIconCheck.Top + DesktopIconCheck.Height + ScaleY(8);
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = wpWelcome) or (PageID = wpReady);
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then
  begin
    WizardForm.RunList.Checked[0] := False;
    WizardForm.RunList.Checked[1] := False;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  desktopShortcutPath: string;
begin
  Result := True;

  if CurPageID <> wpFinished then
    exit;

  if (DesktopIconCheck <> nil) and not DesktopIconCheck.Checked then
  begin
    desktopShortcutPath := ExpandConstant('{autodesktop}\{#MyAppName}.lnk');
    if FileExists(desktopShortcutPath) then
      DeleteFile(desktopShortcutPath);
  end;
end;

procedure InitializeUninstallProgressForm();
var
  Form: TUninstallProgressForm;
begin
  Form := GetUninstallProgressForm();
  RemoveUserDataCheck := TNewCheckBox.Create(Form);
  RemoveUserDataCheck.Parent := Form.InnerPage;
  RemoveUserDataCheck.Left := Form.StatusLabel.Left;
  RemoveUserDataCheck.Top := Form.ProgressBar.Top + Form.ProgressBar.Height + ScaleY(12);
  RemoveUserDataCheck.Width := Form.ProgressBar.Width;
  RemoveUserDataCheck.Caption := ExpandConstant('{cm:RemoveUserDataOnUninstall}');
  RemoveUserDataCheck.Checked := False;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  userDataDir: string;
begin
  if CurUninstallStep <> usPostUninstall then
    exit;

  if (RemoveUserDataCheck = nil) or not RemoveUserDataCheck.Checked then
    exit;

  userDataDir := ExpandConstant('{localappdata}\ankismart');
  if DirExists(userDataDir) then
    DelTree(userDataDir, True, True, True);
end;
