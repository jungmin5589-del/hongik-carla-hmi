@echo off
cd /d "%~dp0"
set "HONGIK_NUREC_LAUNCH_PYTHON=%~dp0..\python\python.exe"
if not exist "%HONGIK_NUREC_LAUNCH_PYTHON%" set "HONGIK_NUREC_LAUNCH_PYTHON=C:\CARLA_0.9.16\diagnostics\nurec-env\Scripts\python.exe"
"%HONGIK_NUREC_LAUNCH_PYTHON%" "%~dp0render_options.py"
if errorlevel 1 pause
