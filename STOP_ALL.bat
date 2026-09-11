@echo off
title WebVeil - Stop All Services
color 0C
cls

echo =====================================================================
echo                 STOPPING ALL WEBVEIL SERVICES
echo =====================================================================
echo.

echo [1/3] Closing WebVeil windows...
taskkill /f /fi "WINDOWTITLE eq WebVeil Reasoning Server*" >nul 2>nul
taskkill /f /fi "WINDOWTITLE eq WebVeil Test Server*" >nul 2>nul
taskkill /f /fi "WINDOWTITLE eq WebVeil Dashboard*" >nul 2>nul
taskkill /f /fi "WINDOWTITLE eq WebVeil - Master Launcher*" >nul 2>nul

echo [2/3] Freeing Port 8000 (Reasoning Server)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000.*LISTENING"') do taskkill /f /pid %%a >nul 2>nul

echo [3/3] Freeing Port 8080 (Test Server)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8080.*LISTENING"') do taskkill /f /pid %%a >nul 2>nul

echo [4/4] Freeing Port 5173 (Frontend)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173.*LISTENING"') do taskkill /f /pid %%a >nul 2>nul

echo.
echo [DONE] All WebVeil background servers have been stopped.
echo.
pause
