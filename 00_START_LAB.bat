@echo off
if not exist "%~dp0live\59_LAB_ONE_CLICK.bat" (
 echo Run this file from the root of the complete portable lab folder.
 pause
 exit /b 1
)
call "%~dp0live\59_LAB_ONE_CLICK.bat" %*
