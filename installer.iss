; ==============================================================================
; KỊCH BẢN ĐÓNG GÓI BỘ CÀI ĐẶT TỰ ĐỘNG CHO WINDOWS (INNO SETUP)
; Phần mềm: PDF AI Marker v3 — Chuyển hồ sơ xây dựng sang AI chuẩn cấu trúc
; Tác giả: Nguyễn Bảo Tú (23HG) — Email: baotuhg@gmail.com
; ==============================================================================

#define MyAppName "PDF AI Marker"
#define MyAppVersion "3.0"
#define MyAppPublisher "Nguyễn Bảo Tú (23HG)"
#define MyAppURL "https://github.com/baotuhg/PDF_AI_Marker"
#define MyAppExeName "PDF_AI_Marker.exe"
#define MyAppSourceDir "PDF_AI_Marker_Windows_EXE_Final2"

[Setup]
; Thông tin định danh ứng dụng (GUID duy nhất)
AppId={{C8E7D6F5-A4B3-4210-9F1E-78D9C0A1B2C3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Đường dẫn cài đặt mặc định
DefaultDirName={autopf}\{#MyAppName} v3
DefaultGroupName={#MyAppName} v3
DisableProgramGroupPage=yes

; Nén thuật toán LZMA2 mạnh nhất để file cài đặt đạt dung lượng nhỏ nhất
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Thông tin file xuất ra
OutputDir=.
OutputBaseFilename=PDF_AI_Marker_v3_Setup
SetupIconFile={#MyAppSourceDir}\app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; Quyền hạn & Giao diện
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
DisableDirPage=no

[Languages]
Name: "vi"; MessagesFile: "compiler:Languages\Vietnamese.isl,compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng trên Màn hình chính (Desktop)"; GroupDescription: "Tùy chọn bổ sung:"

[Files]
; Sao chép toàn bộ thư mục ứng dụng (loại trừ các file bí mật và file rác)
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.lic,keygen.py,*.bak_*,*.tmp,build\*,dist\*"

[Icons]
Name: "{group}\{#MyAppName} v3"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Hướng dẫn sử dụng"; Filename: "{app}\HUONG_DAN_SU_DUNG.txt"
Name: "{group}\Gỡ cài đặt {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName} v3"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Chạy phần mềm ngay sau khi cài đặt hoàn tất
Filename: "{app}\{#MyAppExeName}"; Description: "Khởi động {#MyAppName} v3 ngay bây giờ"; Flags: nowait postinstall skipifsilent
