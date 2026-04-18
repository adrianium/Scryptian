@echo off
title Scryptian Launcher
echo.
echo  ============================================
echo   Scryptian - Local AI Command Bar
echo  ============================================
echo.

REM -- Check Python --
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python not found.
    echo  Please install it from: https://python.org
    echo  Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)
echo  [OK] Python found.

REM -- Check Ollama --
ollama --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Ollama not found.
    echo  It is the engine for your local AI.
    echo  Get it here: https://ollama.com
    echo.
    pause
    exit /b 1
)
echo  [OK] Ollama found.

REM -- Install dependencies --
echo  [..] Installing dependencies...
pip install -r "%~dp0requirements.txt" -q >nul 2>&1
echo  [OK] Dependencies installed.

REM -- Add to Startup --
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTUP%\Scryptian.bat"

if not exist "%SHORTCUT%" (
    (
        echo @echo off
        echo cd /d "%~dp0"
        echo start "" pythonw "%~dp0main.py"
    ) > "%SHORTCUT%"
    echo  [OK] Added to Startup - Scryptian will run on boot.
) else (
    echo  [OK] Already in Startup.
)

REM -- Start Ollama --
echo  [..] Starting Ollama...
powershell -Command "Start-Process ollama -ArgumentList 'serve' -WindowStyle Hidden" >nul 2>&1
timeout /t 3 /nobreak >nul
echo  [OK] Ollama is running.

REM -- Kill old instances --
taskkill /f /im pythonw.exe >nul 2>&1

REM -- Launch --
echo.
echo  Starting Scryptian...
echo  Press Ctrl+Alt to open the command bar.
echo.

cd /d "%~dp0"
pythonw main.py
echo.
echo  Scryptian is running in background.
pause