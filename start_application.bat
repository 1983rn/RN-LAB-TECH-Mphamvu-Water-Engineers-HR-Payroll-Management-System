@echo off
echo ========================================
echo MPHAMVU WATER ENGINEERS
echo Enterprise Management System
echo ========================================
echo.

echo Starting application...
echo.

cd /d "%~dp0"

echo Checking Python installation...
python --version
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)
echo.

echo Installing/Updating dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo.

echo Starting Flask application...
echo.
echo Application will be available at:
echo http://localhost:5001
echo.
echo Press Ctrl+C to stop the server
echo.

python app.py

pause
