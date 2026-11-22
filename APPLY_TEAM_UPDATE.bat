@echo off
set "HONGIK_TEAM_TARGET=%~1"
if not defined HONGIK_TEAM_TARGET set "HONGIK_TEAM_TARGET=%~dp0..\Hongik-CARLA-Lab-20261107"
if not exist "%HONGIK_TEAM_TARGET%\python\python.exe" (
 echo Drag the complete existing Hongik-CARLA-Lab-20261107 folder onto this file.
 pause
 exit /b 1
)
"%HONGIK_TEAM_TARGET%\python\python.exe" -X utf8 "%~dp0apply_team_update.py" --target-bundle "%HONGIK_TEAM_TARGET%"
if errorlevel 1 echo UPDATE STOPPED. Keep the error message and check the guide.
pause
