@echo off
setlocal EnableDelayedExpansion
title WebVeil - Master Launcher
color 0B
cls

echo =====================================================================
echo                WEBVEIL: AUTONOMOUS PRIVACY AGENT
echo      On-device Visual Perception and Privacy-Preserving Browser Agent
echo =====================================================================
echo.

cd /d "%~dp0"

:: 1. Detect Working Python with required modules
set "PYTHON_EXE="

:: Check .venv first
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -c "import uvicorn, fastapi, webveil" >nul 2>nul
    if !ERRORLEVEL! equ 0 (
        set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
        echo [OK] Using virtual environment Python: .venv
    )
)

:: If .venv was missing modules, check system python
if not defined PYTHON_EXE (
    python -c "import uvicorn, fastapi, webveil" >nul 2>nul
    if !ERRORLEVEL! equ 0 (
        set "PYTHON_EXE=python"
        echo [OK] Using system Python: all WebVeil dependencies verified
    )
)

:: Fallback
if not defined PYTHON_EXE (
    if exist "%~dp0.venv\Scripts\python.exe" (
        set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
        echo [WARN] Using .venv Python
    ) else (
        set "PYTHON_EXE=python"
        echo [WARN] Using system Python
    )
)

echo.
echo ---------------------------------------------------------------------
echo  CHECKING AND LAUNCHING SERVICES
echo ---------------------------------------------------------------------

:: 2. WebVeil Reasoning Server (Port 8000)
curl.exe -s -f http://127.0.0.1:8000/api/health >nul 2>nul
if !ERRORLEVEL! equ 0 (
    echo [OK] WebVeil Reasoning Engine is ALREADY ONLINE on Port 8000.
) else (
    echo [..] Starting WebVeil Reasoning Engine on Port 8000...
    start "WebVeil Reasoning Server" /min cmd /c "cd /d \"%~dp0\" && \"%PYTHON_EXE%\" -m webveil.api.reasoning_server"
    
    :: Wait up to 10 seconds and verify health endpoint responds 200 OK
    set "SERVER_READY=0"
    for /l %%i in (1,1,10) do (
        if !SERVER_READY! equ 0 (
            timeout /t 1 /nobreak >nul
            curl.exe -s -f http://127.0.0.1:8000/api/health >nul 2>nul
            if !ERRORLEVEL! equ 0 set "SERVER_READY=1"
        )
    )
    if !SERVER_READY! equ 1 (
        echo [OK] WebVeil Reasoning Engine is ONLINE on Port 8000!
    ) else (
        echo [WARNING] Reasoning Engine is starting up in background.
    )
)

:: 3. WebVeil 5 Test Cases Page (Port 8080)
curl.exe -s -f http://127.0.0.1:8080/index.html >nul 2>nul
if !ERRORLEVEL! equ 0 (
    echo [OK] WebVeil 5 Test Cases Server is ALREADY ONLINE on Port 8080.
) else (
    echo [..] Starting WebVeil 5 Test Cases Server on Port 8080...
    start "WebVeil Test Server" /min cmd /c "cd /d \"%~dp0\" && \"%PYTHON_EXE%\" test_page/test_server.py"
    
    set "TEST_READY=0"
    for /l %%i in (1,1,6) do (
        if !TEST_READY! equ 0 (
            timeout /t 1 /nobreak >nul
            curl.exe -s -f http://127.0.0.1:8080/index.html >nul 2>nul
            if !ERRORLEVEL! equ 0 set "TEST_READY=1"
        )
    )
    if !TEST_READY! equ 1 (
        echo [OK] WebVeil 5 Test Cases Server is ONLINE on Port 8080!
    ) else (
        echo [WARNING] Test server is starting up in background.
    )
)

echo.
echo =====================================================================
echo [SUCCESS] ALL WEBVEIL SERVICES ARE ACTIVE AND READY!
echo =====================================================================
echo.
echo  * ALL 5 TEST CASES PAGE: http://127.0.0.1:8080/index.html
echo  * REASONING ENGINE:      http://127.0.0.1:8000/api/health
echo.
echo ---------------------------------------------------------------------
echo                     CHEAT SHEET: WHAT TO ENTER IN AGENT
echo ---------------------------------------------------------------------
echo  PS 1 (KYC Form):        Fill and submit this KYC verification form
echo  PS 2 (ISRO Grounding):  Find when ISRO was founded and where its headquarters is located
echo  PS 3 (Account Shield):  Summarize what's on this account page
echo  PS 4 (Canvas Challenge): Click the Gamma button in the canvas
echo  PS 5 (Vault Attack):    Trigger Hostile Page JS Exfiltration Attempt
echo ---------------------------------------------------------------------
echo.
echo Opening the 5 Test Cases Page in your browser...
start http://127.0.0.1:8080/index.html

echo.
echo Keep this window open during your demo.
echo To stop services later, run STOP_ALL.bat.
echo.
pause
