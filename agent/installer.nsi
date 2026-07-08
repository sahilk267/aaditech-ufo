; AADITECH UFO Agent — Windows installer (NSIS).
; Build with: makensis /DAGENT_VERSION=x.y.z /DAGENT_EXE_PATH=path\to\aaditech-agent.exe agent\installer.nsi
; Produces:   AaditechUfoAgentSetup-<version>.exe alongside the script.

!ifndef AGENT_VERSION
  !define AGENT_VERSION "0.0.0"
!endif

!ifndef AGENT_EXE_PATH
  !define AGENT_EXE_PATH "..\dist\aaditech-agent.exe"
!endif

Name "AADITECH UFO Agent ${AGENT_VERSION}"
OutFile "AaditechUfoAgentSetup-${AGENT_VERSION}.exe"
InstallDir "$PROGRAMFILES64\AaditechUfo\Agent"
RequestExecutionLevel admin
ShowInstDetails show
ShowUninstDetails show
SetCompressor /SOLID lzma

VIProductVersion "${AGENT_VERSION}.0"
VIAddVersionKey "ProductName"     "AADITECH UFO Agent"
VIAddVersionKey "CompanyName"     "Aaditech"
VIAddVersionKey "FileDescription" "Universal Observability host agent"
VIAddVersionKey "FileVersion"     "${AGENT_VERSION}"
VIAddVersionKey "ProductVersion"  "${AGENT_VERSION}"

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

; ── Install ───────────────────────────────────────────────────────────────────
Section "Install"
  SetOutPath "$INSTDIR"

  ; Stop any running agent process before installing (ignore errors)
  ExecWait 'taskkill /F /IM aaditech-agent.exe' $0

  ; Copy the prebuilt agent binary.
  File "/oname=aaditech-agent.exe" "${AGENT_EXE_PATH}"

  ; Stamp version into the install dir.
  FileOpen $0 "$INSTDIR\version.txt" w
  FileWrite $0 "${AGENT_VERSION}$\r$\n"
  FileClose $0

  ; Register uninstaller.
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AaditechUfoAgent" \
    "DisplayName" "AADITECH UFO Agent"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AaditechUfoAgent" \
    "DisplayVersion" "${AGENT_VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AaditechUfoAgent" \
    "Publisher" "Aaditech"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AaditechUfoAgent" \
    "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AaditechUfoAgent" \
    "UninstallString" "$\"$INSTDIR\Uninstall.exe$\""
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AaditechUfoAgent" \
    "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AaditechUfoAgent" \
    "NoRepair" 1

  ; Start menu shortcut for manual launches.
  CreateDirectory "$SMPROGRAMS\AADITECH UFO"
  CreateShortcut  "$SMPROGRAMS\AADITECH UFO\Agent.lnk" "$INSTDIR\aaditech-agent.exe"
SectionEnd

; ── Uninstall ─────────────────────────────────────────────────────────────────
Section "Uninstall"
  ; 1. Stop the agent process so files aren't locked
  ExecWait 'taskkill /F /IM aaditech-agent.exe' $0

  ; 2. Remove ALL files in the install directory, including:
  ;    - aaditech-agent.exe (the binary)
  ;    - version.txt
  ;    - .env (config written by onboarding script)
  ;    - agent_data.db, agent_outbox.db (SQLite runtime databases)
  ;    - *.log (any log files written by the agent)
  ;    - Uninstall.exe itself
  RMDir /r "$INSTDIR"

  ; 3. Remove start menu shortcuts
  Delete "$SMPROGRAMS\AADITECH UFO\Agent.lnk"
  RMDir  "$SMPROGRAMS\AADITECH UFO"

  ; 4. Remove registry uninstall entry
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AaditechUfoAgent"
SectionEnd
