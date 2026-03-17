@echo off
chcp 65001 >nul
echo ========================================
echo   GeoAgent Backend Server
echo ========================================
echo.

cd /d %~dp0backend

echo [1/2] Activating virtual environment...
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo WARNING: No virtual environment found, using system Python
)

echo [2/2] Starting uvicorn on port 8000...
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
