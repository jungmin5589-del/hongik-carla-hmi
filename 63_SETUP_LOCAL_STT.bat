@echo off
cd /d "%~dp0"
py -3.12 stt_setup.py
if errorlevel 1 (
 echo Local STT needs a separate system Python 3.12 installation.
 echo CARLA dependencies were not changed.
)
pause
