@echo off
title SceneForge updater
echo.
echo  Updating SceneForge to the latest version.
echo  Please CLOSE the SceneForge window first if it is open.
echo  Your projects, presets, Python, FFmpeg and speech model are kept.
echo.
pause
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\update.ps1"
echo.
pause
