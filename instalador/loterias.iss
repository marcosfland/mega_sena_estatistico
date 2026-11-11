; Instalador do Loterias Estatístico (Inno Setup 6).
; Compilado pelo GitHub Actions (.github/workflows/instalador.yml):
;   iscc /DAppVersion=2.1.0 /DSourceDir=dist\LoteriasEstatistico /DOutputDir=saida instalador\loterias.iss
; Instala por usuário (sem pedir administrador). Banco, preferências e logs ficam em
; %LOCALAPPDATA%\LoteriasEstatistico e são preservados ao atualizar ou desinstalar.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\LoteriasEstatistico"
#endif
#ifndef OutputDir
  #define OutputDir "..\saida"
#endif
#define AppName "Loterias Estatístico"
#define AppExe "LoteriasEstatistico.exe"

[Setup]
AppId={{8B5E2C1A-4F7D-4C3B-9A61-2D7E5F0C9A13}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Marcos Land
AppPublisherURL=https://github.com/marcosfland/mega_sena_estatistico
AppSupportURL=https://github.com/marcosfland/mega_sena_estatistico/issues
DefaultDirName={autopf}\LoteriasEstatistico
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#OutputDir}
OutputBaseFilename=LoteriasEstatistico-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExe}
CloseApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Remove arquivos de versões anteriores que não existem mais no pacote novo.
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
