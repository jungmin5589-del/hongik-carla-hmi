@echo off
cd /d "%~dp0"
if not exist "..\python\python.exe" (
 echo The portable python folder is required beside live.
 pause
 exit /b 1
)
"..\python\python.exe" -X utf8 "%~dp0launch_native_carla.py" --stop
if errorlevel 1 pause
