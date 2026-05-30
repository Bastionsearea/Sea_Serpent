@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   Sea Serpent - Setup ^& Launch
echo ============================================
echo.

:: Try to find Python — try multiple approaches
set "PYTHON="

:: 1. Try python (PATH or current dir)
where python >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%i in ('where python') do set "PYTHON=%%i"
    goto :found
)

:: 2. Try python3
where python3 >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%i in ('where python3') do set "PYTHON=%%i"
    goto :found
)

:: 3. Try py launcher (installed by python.org even without PATH)
where py >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%i in ('where py') do set "PYTHON=%%i"
    goto :found
)

:: 4. Scan common install locations
for %%d in (
    "%LOCALAPPDATA%\Programs\Python"
    "C:\Program Files\Python*"
    "C:\Python*"
    "%LOCALAPPDATA%\Microsoft\WindowsApps"
) do (
    for /f "delims=" %%f in ('dir /b /s "%%~d\python.exe" 2^>nul ^| sort /r') do (
        set "PYTHON=%%f"
        goto :found
    )
)

echo [ERROR] Python not found on this system.
echo.
echo Please install Python 3.9+ from: https://www.python.org/downloads/
echo During installation, check the box: "Add Python to PATH"
echo.
pause
exit /b 1

:found
echo [OK] Python found: !PYTHON!
!PYTHON! --version
echo.

:: Ensure pip is available
!PYTHON! -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] pip not available. Trying to install pip...
    !PYTHON! -m ensurepip --upgrade
)

:: Create venv if not exists
if not exist "venv\" (
    echo [INFO] Creating virtual environment...
    !PYTHON! -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)

:: Activate
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate venv.
    pause
    exit /b 1
)

:: Install dependencies
echo [INFO] Installing dependencies...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo [OK] Dependencies installed.

:: Launch
echo.
echo [INFO] Launching Sea Serpent...
start "" python main.py

echo [OK] Application started. You can close this window.
timeout /t 3 >nul
exit
