; ====================================================================
;  바른자세 — Inno Setup 설치 스크립트
;  빌드: ISCC.exe installer.iss
; ====================================================================

#define MyAppName "바른자세"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "PostureApp"
#define MyAppExeName "바른자세.exe"
#define MyAppId "{{A7F3C2E1-9B4D-4E6A-8C1F-2D5E7A9B3C4D}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
; 설치 폴더는 ASCII로 고정한다. mediapipe C++ 리소스 로더가 경로의 한글을
; 처리하지 못하므로(자세 인식 실패), 표시 이름은 한글이어도 폴더는 영문으로 둔다.
DefaultDirName={autopf}\PostureApp
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; 관리자 권한 없이 사용자 폴더에 설치 (UAC 프롬프트 회피)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer
OutputBaseFilename=바른자세-설치-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; 64비트 전용 빌드
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; PyInstaller 산출물 폴더 전체를 통째로 포함
Source: "dist\PostureApp\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
