@echo off
rem Experimental installer: Windows end-to-end hardware testing is pending.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -EnableUntested
pause
