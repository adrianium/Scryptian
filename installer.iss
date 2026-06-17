#define MyAppName "Scryptian"
#define MyAppVersion "0.3.7"
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

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    KillScryptian();
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDataDir: string;
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    Exec('powershell', '-NonInteractive -WindowStyle Hidden -Command "$id=''unknown''; $f=$env:LOCALAPPDATA+''\Scryptian\.id''; if(Test-Path $f){$id=(Get-Content $f -Raw).Trim()}; $mid=[System.BitConverter]::ToString([System.Security.Cryptography.MD5]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($env:COMPUTERNAME))).Replace(''-'','''').ToLower().Substring(0,16); $body=''{\\"api_key\\":\\"phc_nyYF49YRbnnsjJbMqFwZbXxpiPfU249NAnmnZHuPavei\\",\\"event\\":\\"uninstalled\\",\\"distinct_id\\":\\\"''+$id+''\\"\ ,\\"properties\\":{\\"machine_id\\":\\\"''+$mid+''\\\"}}'' ; try{Invoke-WebRequest -Uri ''https://us.i.posthog.com/capture/'' -Method POST -ContentType ''application/json'' -Body $body -TimeoutSec 5}catch{}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
  if CurUninstallStep = usPostUninstall then
  begin
    AppDataDir := ExpandConstant('{localappdata}\Scryptian');
    if MsgBox('Remove all data including downloaded AI model?' + #13#10 + AppDataDir, mbConfirmation, MB_YESNO) = IDYES then
      DelTree(AppDataDir, True, True, True);
  end;
end;
