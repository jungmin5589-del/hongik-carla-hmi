@echo off
cd /d "%~dp0"
set "HONGIK_NUREC_STOP_PYTHON=%~dp0..\python\python.exe"
if not exist "%HONGIK_NUREC_STOP_PYTHON%" set "HONGIK_NUREC_STOP_PYTHON=C:\CARLA_0.9.16\diagnostics\nurec-env\Scripts\python.exe"
"%HONGIK_NUREC_STOP_PYTHON%" "%~dp0stop_nurec_lab.py"
pause
