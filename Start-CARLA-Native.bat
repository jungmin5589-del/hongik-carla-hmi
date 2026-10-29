@echo off
setlocal
set OPENBLAS_NUM_THREADS=1
set OMP_NUM_THREADS=2
set MKL_NUM_THREADS=1
"C:\CARLA_0.9.16\diagnostics\nurec-env\Scripts\python.exe" "%~dp0launch_native_carla.py"
if errorlevel 1 pause
