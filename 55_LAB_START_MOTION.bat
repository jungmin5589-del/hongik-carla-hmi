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
echo.
echo  6DOF ON: data-server-py sends MotionHouse UDP packets (default 127.0.0.1:10000)
echo  and serves WebSocket telemetry on port 8765.
echo  First run: nobody on the rig. Confirm the rig's neutral and emergency-stop
echo  procedure with the lab staff before continuing. Close this window to cancel.
echo.
pause
"..\python\python.exe" lab_one_click.py --motion %*
if errorlevel 1 pause
