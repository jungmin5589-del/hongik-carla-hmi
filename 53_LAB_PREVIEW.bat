@echo off
cd /d "%~dp0"
"..\python\python.exe" launch_lab.py --preview
if errorlevel 1 pause
