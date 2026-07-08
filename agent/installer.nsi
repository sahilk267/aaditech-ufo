; AADITECH UFO Agent — Windows NSIS installer with Windows Service support.
;
; Build with:
;   makensis /DAGENT_VERSION=x.y.z /DAGENT_EXE_PATH=path\to\aaditech-agent.exe agent\installer.nsi
;
; Produces: AaditechUfoAgentSetup-<version>.exe
;
; The installer:
;   - Stops + removes any previous AaditechAgent Windows service
;   - Installs aaditech-agent.exe + nssm.exe to $INSTDIR
;   - Registers the agent as a Windows service (auto-start, restarts on crash)
;   - Writes registry uninstall info for Add/Remove Programs
;
; The uninstaller:
;   - Stops + removes the Windows service
;   - Kills any stray processes
;   - Removes ALL files in $INSTDIR (including runtime .env, .db, logs)
;   - Cleans up registry + start menu

!ifndef AGENT_VERSION
  !define AGENT_VERSION "0.0.0"
!endif

!ifndef AGENT_EXE_PATH
  !define AGENT_EXE_PATH "..\dist\aaditech-agent.exe"
!endif

!ifndef NSSM_EXE_PATH
  !define NSSM_EXE_PATH "..\dist\nssm.exe"
!endif

!define SERVICE_NAME   "AaditechAgent"
!define SERVICE_DISPLAY "Aaditech UFO Agent"
!define SERVICE_DESC   "Universal Observability monitoring agent — reports metrics to the Aaditech UFO platform."

Name "${SERVICE_DISPLAY} ${AGENT_VERSION}"
OutFile "AaditechUfoAgentSetup-${AGENT_VERSION}.exe"
InstallDir "$PROGRAMFILES64\AaditechUfo\Agent"
RequestExecutionLevel admin
ShowInstDetails show
ShowUninstDetails show
SetCompressor /SOLID lzma

VIProductVersion "${AGENT_VERSION}.0"
VIAddVersionKey "ProductName"     "${SERVICE_DISPLAY}"
VIAddVersionKey "CompanyName"     "Aaditech"
VIAddVersionKey "FileDescription" "Universal Observability host agent installer"
VIAddVersionKey "FileVersion"     "${AGENT_VERSION}"
VIAddVersionKey "ProductVersion"  "${AGENT_VERSION}"
VIAddVersionKey "LegalCopyright"  "Aaditech"

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

; ── Macros ────────────────────────────────────────────────────────────────────

; Run a command silently via cmd and ignore its exit code
!macro ExecSilent CMD
  nsExec::ExecToLog /TIMEOUT=15000 '${CMD}'
  Pop $0
!macroend

; ── Install ───────────────────────────────────────────────────────────────────
Section "Install"
  SetOutPath "$INSTDIR"

  ; ── 1. Stop + remove old service (if upgrading) ──────────────────────────
  DetailPrint "Stopping existing service (if any)..."
  !insertmacro ExecSilent '"$INSTDIR\nssm.exe" stop ${SERVICE_NAME}'
  Sleep 2000
  !insertmacro ExecSilent '"$INSTDIR\nssm.exe" remove ${SERVICE_NAME} confirm'
  ; Fallback: kill stray process
  !insertmacro ExecSilent 'taskkill /F /IM aaditech-agent.exe'
  Sleep 1000

  ; ── 2. Install files ─────────────────────────────────────────────────────
  File "/oname=aaditech-agent.exe" "${AGENT_EXE_PATH}"
  File "/oname=nssm.exe"           "${NSSM_EXE_PATH}"

  ; Stamp version
  FileOpen  $0 "$INSTDIR\version.txt" w
  FileWrite $0 "${AGENT_VERSION}$\r$\n"
  FileClose $0

  ; ── 3. Register the Windows service via NSSM ─────────────────────────────
  ;
  ;  NSSM wraps any .exe as a proper Windows service:
  ;    • Handles SERVICE_CONTROL_STOP / PAUSE / CONTINUE signals
  ;    • Restarts the process automatically on crash
  ;    • Captures stdout/stderr to a log file
  ;    • Sets working directory so .env is found at $INSTDIR\.env
  ;
  DetailPrint "Installing Windows service '${SERVICE_NAME}'..."
  nsExec::ExecToLog /TIMEOUT=15000 \
    '"$INSTDIR\nssm.exe" install ${SERVICE_NAME} "$INSTDIR\aaditech-agent.exe"'
  Pop $0

  ; Service metadata
  nsExec::ExecToLog \
    '"$INSTDIR\nssm.exe" set ${SERVICE_NAME} DisplayName "${SERVICE_DISPLAY}"'
  Pop $0
  nsExec::ExecToLog \
    '"$INSTDIR\nssm.exe" set ${SERVICE_NAME} Description "${SERVICE_DESC}"'
  Pop $0

  ; Working directory — agent reads .env from here
  nsExec::ExecToLog \
    '"$INSTDIR\nssm.exe" set ${SERVICE_NAME} AppDirectory "$INSTDIR"'
  Pop $0

  ; Start type: auto (starts with Windows)
  nsExec::ExecToLog \
    '"$INSTDIR\nssm.exe" set ${SERVICE_NAME} Start SERVICE_AUTO_START'
  Pop $0

  ; Restart policy: restart on crash/failure with back-off
  ;   AppRestartDelay  — milliseconds to wait before restarting (5 s)
  ;   AppThrottle      — minimum run-time (ms) before a restart is allowed (30 s)
  nsExec::ExecToLog \
    '"$INSTDIR\nssm.exe" set ${SERVICE_NAME} AppExit Default Restart'
  Pop $0
  nsExec::ExecToLog \
    '"$INSTDIR\nssm.exe" set ${SERVICE_NAME} AppRestartDelay 5000'
  Pop $0
  nsExec::ExecToLog \
    '"$INSTDIR\nssm.exe" set ${SERVICE_NAME} AppThrottle 30000'
  Pop $0

  ; Redirect stdout/stderr to log files inside $INSTDIR
  nsExec::ExecToLog \
    '"$INSTDIR\nssm.exe" set ${SERVICE_NAME} AppStdout "$INSTDIR\agent-stdout.log"'
  Pop $0
  nsExec::ExecToLog \
    '"$INSTDIR\nssm.exe" set ${SERVICE_NAME} AppStderr "$INSTDIR\agent-stderr.log"'
  Pop $0
  ; Rotate logs when they exceed 10 MB
  nsExec::ExecToLog \
    '"$INSTDIR\nssm.exe" set ${SERVICE_NAME} AppStdoutCreationDisposition 4'
  Pop $0
  nsExec::ExecToLog \
    '"$INSTDIR\nssm.exe" set ${SERVICE_NAME} AppRotateFiles 1'
  Pop $0
  nsExec::ExecToLog \
    '"$INSTDIR\nssm.exe" set ${SERVICE_NAME} AppRotateBytes 10485760'
  Pop $0

  ; ── 4. Start the service ─────────────────────────────────────────────────
  DetailPrint "Starting service '${SERVICE_NAME}'..."
  nsExec::ExecToLog /TIMEOUT=20000 \
    '"$INSTDIR\nssm.exe" start ${SERVICE_NAME}'
  Pop $0

  ; ── 5. Register uninstaller + Add/Remove Programs ────────────────────────
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${SERVICE_NAME}" \
    "DisplayName"     "${SERVICE_DISPLAY}"
  WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${SERVICE_NAME}" \
    "DisplayVersion"  "${AGENT_VERSION}"
  WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${SERVICE_NAME}" \
    "Publisher"       "Aaditech"
  WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${SERVICE_NAME}" \
    "InstallLocation" "$INSTDIR"
  WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${SERVICE_NAME}" \
    "UninstallString" "$\"$INSTDIR\Uninstall.exe$\""
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${SERVICE_NAME}" \
    "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${SERVICE_NAME}" \
    "NoRepair"  1

  ; ── 6. Start menu shortcut ───────────────────────────────────────────────
  CreateDirectory "$SMPROGRAMS\AADITECH UFO"
  CreateShortcut  "$SMPROGRAMS\AADITECH UFO\Agent.lnk" "$INSTDIR\aaditech-agent.exe"

  DetailPrint "Installation complete. Service '${SERVICE_NAME}' is running."
SectionEnd

; ── Uninstall ─────────────────────────────────────────────────────────────────
Section "Uninstall"
  ; ── 1. Stop + remove the Windows service ─────────────────────────────────
  DetailPrint "Stopping service '${SERVICE_NAME}'..."
  nsExec::ExecToLog /TIMEOUT=20000 \
    '"$INSTDIR\nssm.exe" stop ${SERVICE_NAME}'
  Pop $0
  Sleep 3000

  DetailPrint "Removing service '${SERVICE_NAME}'..."
  nsExec::ExecToLog /TIMEOUT=10000 \
    '"$INSTDIR\nssm.exe" remove ${SERVICE_NAME} confirm'
  Pop $0

  ; ── 2. Kill any stray process ─────────────────────────────────────────────
  !insertmacro ExecSilent 'taskkill /F /IM aaditech-agent.exe'
  Sleep 1000

  ; ── 3. Remove ALL files recursively (including .env, .db, logs) ──────────
  DetailPrint "Removing installation directory..."
  RMDir /r "$INSTDIR"

  ; ── 4. Start menu ─────────────────────────────────────────────────────────
  Delete "$SMPROGRAMS\AADITECH UFO\Agent.lnk"
  RMDir  "$SMPROGRAMS\AADITECH UFO"

  ; ── 5. Registry ───────────────────────────────────────────────────────────
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${SERVICE_NAME}"

  DetailPrint "Uninstall complete."
SectionEnd
