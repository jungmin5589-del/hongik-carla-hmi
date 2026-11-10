@echo off
cd /d "%~dp0"
if not exist "..\python\python.exe" (
 echo The complete portable lab folder is required. Copy live, python, cache and the engine together.
 pause
 exit /b 1
)
"..\python\python.exe" lab_one_click.py %*
if errorlevel 1 (
 echo Startup stopped. Keep this message for the lab connection check.
 pause
 exit /b 1
)
