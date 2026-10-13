@echo off
title SceneForge - close this window to stop SceneForge
cd /d "%~dp0"
if not exist "python\python.exe" (
  echo SceneForge is not installed yet. Double-click Install_SceneForge.bat in this folder first.
  pause
  exit /b 1
)
set "PATH=%~dp0ffmpeg\bin;%PATH%"
echo Starting SceneForge... your browser will open in a few seconds.
"python\python.exe" app.py
if errorlevel 1 (
  echo.
  echo SceneForge stopped with an error. See the messages above.
  pause
)
