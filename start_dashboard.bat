@echo off
REM GuardPaw Dashboard Launcher for Windows
REM Starts the Flask API backend and opens the dashboard in browser

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo ========================================
echo     GUARDPAW DASHBOARD LAUNCHER
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8+
    pause
    exit /b 1
)

echo [*] Installing dependencies...
pip install flask flask-cors -q

echo [+] Dependencies ready
echo.
echo [*] Starting GuardPaw API Server...
echo.

REM Start the Flask API
python app/api.py

pause
