; Aaditech UFO Agent Uninstaller Script
; Usage: makensis uninstaller.nsi

!include "MUI2.nsh"

Name "Aaditech UFO Agent"
OutFile "aaditech-agent-uninstaller.exe"
InstallDir "$PROGRAMFILES\Aaditech\UFOAgent"
RequestExecutionLevel admin

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

Section "Uninstall"
	DetailPrint "Stopping and removing Aaditech Agent..."

	ExecWait 'taskkill /F /IM aaditech-agent.exe'
	Delete "$INSTDIR\aaditech-agent.exe"
	Delete "$INSTDIR\.env"
	Delete "$INSTDIR\README_AGENT.md"

	RMDir "$INSTDIR"
	RMDir "$PROGRAMFILES\Aaditech"

	DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AaditechUFOAgent"

	DetailPrint "Uninstall completed"
SectionEnd
