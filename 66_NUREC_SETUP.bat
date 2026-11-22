@echo off
cd /d "%~dp0"
set "HONGIK_NUREC_SETUP_PYTHON=%~dp0..\python\python.exe"
if not exist "%HONGIK_NUREC_SETUP_PYTHON%" set "HONGIK_NUREC_SETUP_PYTHON=C:\CARLA_0.9.16\diagnostics\nurec-env\Scripts\python.exe"
"%HONGIK_NUREC_SETUP_PYTHON%" "%~dp0setup_nurec_lab.py" --prepare --portable-python
pause
