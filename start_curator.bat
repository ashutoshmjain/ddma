@echo off
cd /d "%~dp0"
title DDMA Clip Curator Server
echo ==================================================
echo       DDMA Clip Curator Server Launcher
echo ==================================================
echo.
echo Launching the DDMA Clip Curator Server...
echo.
python scratch/run_curator.py
echo.
echo Server has stopped.
pause
