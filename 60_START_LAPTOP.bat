@echo off
cd /d "%~dp0"
"..\python\python.exe" -X utf8 start_profile.py --profile laptop %*
if errorlevel 1 pause
