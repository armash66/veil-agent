@echo off
title WebVeil - Automatic Agent & Server Launcher
color 0B
cls
echo =====================================================================
echo                WEBVEIL: AUTONOMOUS PRIVACY AGENT
echo      On-device Visual Perception & Privacy-Preserving Browser Agent
echo =====================================================================
echo.
echo [1/3] Checking Python environment...
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python was not found in PATH! Please install Python 3.10+.
    pause
    exit /b 1
)

echo [2/3] Starting WebVeil Reasoning Server on Port 8000...
start "WebVeil Reasoning Server (Port 8000)" /min python -m webveil.api.reasoning_server

echo [3/3] Starting WebVeil Test Environment on Port 8080...
start "WebVeil Test Pages (Port 8080)" /min python test_page/test_server.py

echo.
echo [SUCCESS] WebVeil backend servers launched successfully in the background!
echo - Reasoning Engine: http://127.0.0.1:8000/api/health
echo - Test Pages:       http://127.0.0.1:8080/index.html
echo - Web App:          http://localhost:5173/
echo.
echo Opening WebVeil in your default browser...
start http://localhost:5173/

echo.
echo You can keep this window open or minimize it during your pitch presentation.
echo Press any key to close this launcher window.
pause >nul
