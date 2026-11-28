@echo off
set "HONGIK_UI_BUNDLE=%~1"
if not defined HONGIK_UI_BUNDLE (
 echo Drag your existing complete Hongik-CARLA-Lab folder onto this file.
 pause
 exit /b 1
)
if not exist "%HONGIK_UI_BUNDLE%\python\python.exe" (
 echo Complete lab bundle with python and live folders required.
 pause
 exit /b 1
)
"%HONGIK_UI_BUNDLE%\python\python.exe" -X utf8 "%~dp0apply_passenger_ui.py" --target-live "%HONGIK_UI_BUNDLE%\live" --apply
if errorlevel 1 echo UI UPDATE STOPPED. Keep the error message for review.
pause
