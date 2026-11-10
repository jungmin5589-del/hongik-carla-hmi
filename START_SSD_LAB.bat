@echo off
if not exist "%~dp0Hongik-CARLA-Lab-20261107\00_START_LAB.bat" (
 echo The Hongik-CARLA-Lab-20261107 folder must be beside this file.
 pause
 exit /b 1
)
call "%~dp0Hongik-CARLA-Lab-20261107\00_START_LAB.bat" %*
