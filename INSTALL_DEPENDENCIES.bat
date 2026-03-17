@echo off
title Install Dependencies - MPHAMVU WATER ENGINEERS
color 0B

echo.
echo ================================================
echo   MPHAMVU WATER ENGINEERS
echo   Installing System Dependencies
echo ================================================
echo.

cd /d "%~dp0"

echo Checking Python installation...
python --version
if errorlevel 1 (
    echo.
    echo ERROR: Python is not installed!
    echo.
    echo Please download and install Python from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

echo.
echo Python found! Installing dependencies...
echo.
echo NOTE: This may take a few minutes and requires internet connection
echo.

echo Upgrading pip...
python -m pip install --upgrade pip --user

echo.
echo Installing packages (this works with Python 3.14)...
echo.

pip install --user Flask
pip install --user Flask-SQLAlchemy
pip install --user Werkzeug
pip install --user SQLAlchemy
pip install --user reportlab
pip install --user openpyxl
pip install --user Pillow
pip install --user python-dateutil
pip install --user bcrypt
pip install --user email-validator
pip install --user Jinja2

echo.
echo ================================================
echo   Installation Complete!
echo ================================================
echo.
echo You can now run the application using:
echo RUN_APPLICATION.bat
echo.

pause
