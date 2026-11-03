@echo off
setlocal
cd /d "%~dp0"

REM K-line training camp launcher.
REM Keep this file ASCII-only: cmd mangles non-ASCII in .bat on some locales.

echo ============================================
echo   K-line Training Camp
echo ============================================

if exist ".venv\Scripts\python.exe" goto havevenv

echo First run: creating local venv ...
where py >nul 2>nul
if errorlevel 1 (
  python -m venv .venv
) else (
  py -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] could not create venv. Install Python 3.11+ and retry.
  pause
  exit /b 1
)

:havevenv
set "PYEXE=.venv\Scripts\python.exe"

if not exist ".venv\.deps-ok" (
  echo Installing dependencies ^(first run only, may take a minute^) ...
  "%PYEXE%" -m pip install --upgrade pip
  "%PYEXE%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [ERROR] dependency install failed. Check network or use a mirror.
    pause
    exit /b 1
  )
  echo ok> ".venv\.deps-ok"
)

if "%KLINE_DATA_DIR%"=="" (
  echo Data dir: default ^(set KLINE_DATA_DIR to point at your parquet folder^)
) else (
  echo Data dir: %KLINE_DATA_DIR%
)
echo.
echo Starting: http://127.0.0.1:8760   ^(close this window to stop^)
echo.

"%PYEXE%" run.py
pause
