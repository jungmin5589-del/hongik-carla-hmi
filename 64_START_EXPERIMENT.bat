@echo off
cd /d "%~dp0"
if not exist "..\python\python.exe" (
 echo Extract the full portable bundle first.
 pause
 exit /b 1
)
"..\python\python.exe" start_experiment.py
if errorlevel 1 pause
