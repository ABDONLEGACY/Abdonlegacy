@echo off
title SceneForge installer
echo.
echo  Installing SceneForge. This downloads free tools only (Python, FFmpeg, the speech model)
echo  into this folder. It takes 5-15 minutes. Please keep this window open.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\install.ps1"
echo.
pause
