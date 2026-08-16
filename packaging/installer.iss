; Inno Setup — Plain Text Editor. Signed single-file installer, compiled in CI.
#define AppName "Plain Text Editor"
#define AppVersion "1.1.0"

[Setup]
AppMutex=QuickOpen.PlainTextEditor
AppId={{51A0F001-0019-4E5B-8C71-9B0E2F3A0019}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=QuickOpen (quickopen.ai)
AppPublisherURL=https://quickopen.ai/projects/plain-text-editor
DefaultDirName={autopf}\PlainTextEditor
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\PlainTextEditor.exe
OutputDir=dist
OutputBaseFilename=PlainTextEditor-Setup
SetupIconFile=..\plain-text-editor.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
WizardImageFile=branding\wizard-large.bmp
WizardSmallImageFile=branding\wizard-small.bmp
AppCopyright=Apache-2.0. 100%% AI-built, published on QuickOpen (quickopen.ai).
VersionInfoCompany=QuickOpen
VersionInfoProductName=Plain Text Editor
VersionInfoVersion=1.1.0.0
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel2=Plain Text Editor is a 100%% AI-built, open-source offline tool, published on QuickOpen (quickopen.ai).%n%nThis will install it on your computer.
BeveledLabel=QuickOpen · quickopen.ai

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "trustca"; Description: "Trust the QuickOpen Root CA (lets Windows verify QuickOpen signatures)"; GroupDescription: "Security:"; Flags: unchecked

[Files]
Source: "staging\PlainTextEditor.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\quickopen-root.crt"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "staging\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme skipifsourcedoesntexist
Source: "staging\LICENSE"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\Plain Text Editor"; Filename: "{app}\PlainTextEditor.exe"; IconFilename: "{app}\PlainTextEditor.exe"
Name: "{group}\Uninstall Plain Text Editor"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Plain Text Editor"; Filename: "{app}\PlainTextEditor.exe"; IconFilename: "{app}\PlainTextEditor.exe"; Tasks: desktopicon

[Run]
Filename: "certutil.exe"; Parameters: "-addstore -user Root ""{app}\quickopen-root.crt"""; Tasks: trustca; Flags: runhidden; StatusMsg: "Trusting the QuickOpen Root CA..."
Filename: "{app}\PlainTextEditor.exe"; Description: "Launch Plain Text Editor now"; Flags: nowait postinstall skipifsilent

; Full uninstall: remove every app-owned trace. The QuickOpen Root CA is
; intentionally NOT touched — it is shared by all QuickOpen apps.
[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\PlainTextEditor"
