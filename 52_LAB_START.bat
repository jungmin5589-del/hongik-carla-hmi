@echo off
cd /d "%~dp0"
if not exist "..\python\python.exe" (
 echo Extract the full portable lab bundle first.
 pause
 exit /b 1
)
if not exist "..\CARLA_0.9.16\.hongik-engine-ready" (
 echo Run 51_LAB_SETUP.bat once on the lab internal SSD first.
 pause
 exit /b 1
)
"..\python\python.exe" launch_lab.py
if errorlevel 1 pause
