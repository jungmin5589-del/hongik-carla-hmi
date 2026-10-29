@echo off
"C:\CARLA_0.9.16\diagnostics\nurec-env\Scripts\python.exe" "%~dp0launch_native_carla.py" --stop
if errorlevel 1 pause
