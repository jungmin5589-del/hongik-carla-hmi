@echo off
setlocal
set "LAB_LIVE=%~dp0..\live"
if not "%~1"=="" set "LAB_LIVE=%~1"
set "LAB_PYTHON=%~dp0..\python\python.exe"
if not exist "%LAB_PYTHON%" (
  echo Put Git-Setup beside live and python in the delivered lab folder.
  pause
  exit /b 1
)
where git >nul 2>nul
if errorlevel 1 (
  echo Install Git for Windows, then reopen this window.
  echo https://git-scm.com/install/windows
  pause
  exit /b 1
)
"%LAB_PYTHON%" "%~dp0lab_git_setup.py" --live "%LAB_LIVE%"
set "LAB_RESULT=%ERRORLEVEL%"
echo.
echo Read LAB-GIT-WORKFLOW-KO.md for the first commit and push.
pause
exit /b %LAB_RESULT%
