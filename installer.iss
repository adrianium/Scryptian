#define MyAppName "Scryptian"
#define MyAppVersion "0.5.0"
#define MyAppPublisher "adrianium"
#define MyAppURL "https://github.com/adrianium/Scryptian"
#define MyAppExeName "Scryptian.exe"
#define MyAppIcon "icon.ico"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=
InfoBeforeFile=privacy_notice.txt
OutputDir=dist
OutputBaseFilename=Scryptian_Setup
SetupIconFile={#MyAppIcon}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes
CloseApplicationsFilter=Scryptian.exe
RestartApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\Scryptian\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "uninstall_telemetry.ps1"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "taskkill"; Parameters: "/f /im {#MyAppExeName}"; Flags: runhidden

[Code]
procedure KillScryptian();
var
  ResultCode: Integer;
begin
  Exec('taskkill', '/f /im Scryptian.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure CleanOldInstall();
begin
  // Remove old Program Files (x86) installation
  if DirExists('C:\Program Files (x86)\Scryptian') then
    DelTree('C:\Program Files (x86)\Scryptian', True, True, True);
  // Fix registry autostart to point to new location
  RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Scryptian');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    KillScryptian();
    CleanOldInstall();
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDataDir: string;
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    Exec('powershell', '-ExecutionPolicy Bypass -NonInteractive -WindowStyle Hidden -File "' + ExpandConstant('{app}') + '\uninstall_telemetry.ps1"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
  if CurUninstallStep = usPostUninstall then
  begin
    AppDataDir := ExpandConstant('{localappdata}\Scryptian');
    if MsgBox('Remove all data including downloaded AI model?' + #13#10 + AppDataDir, mbConfirmation, MB_YESNO) = IDYES then
      DelTree(AppDataDir, True, True, True);
  end;
end;
