; Script de Inno Setup para Control de Tiempos — Gente Util (v1.0.0)
; Cumple estrictamente la sección 6.2 y RNF-11 del plan:
; - Instala en modo por usuario (PrivilegesRequired=lowest) sin solicitar UAC.
; - Destino en %LOCALAPPDATA%\Programs\ControlTiempos.
; - Accesos directos en el menú Inicio y Escritorio del usuario actual.
; - Inicio automático opcional en HKCU\Software\Microsoft\Windows\CurrentVersion\Run.

#define NombreApp "Control de Tiempos — Gente Util"
#define NombreCorto "ControlTiempos"
#define VersionApp "1.0.0"
#define EmpresaApp "Gente Util"
#define EjecutableApp "ControlTiempos.exe"

[Setup]
AppId={{8D4F69C2-71B3-4E5A-9C1E-43F063A9B4FB}
AppName={#NombreApp}
AppVersion={#VersionApp}
AppPublisher={#EmpresaApp}
DefaultDirName={localappdata}\Programs\{#NombreCorto}
DefaultGroupName={#NombreApp}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
OutputDir=..\dist
OutputBaseFilename=Instalador-{#NombreCorto}-v{#VersionApp}-Usuario
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#EjecutableApp}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Iniciar automáticamente con Windows (minimizada en la bandeja del sistema)"; GroupDescription: "Inicio con Windows:"

[Files]
Source: "..\dist\ControlTiempos\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\docs\manual_usuario.md"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\{#NombreApp}\{#NombreApp}"; Filename: "{app}\{#EjecutableApp}"
Name: "{userdesktop}\{#NombreApp}"; Filename: "{app}\{#EjecutableApp}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#NombreCorto}"; ValueData: """{app}\{#EjecutableApp}"" --bandeja"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#EjecutableApp}"; Description: "Abrir {#NombreApp}"; Flags: nowait postinstall skipifsilent
