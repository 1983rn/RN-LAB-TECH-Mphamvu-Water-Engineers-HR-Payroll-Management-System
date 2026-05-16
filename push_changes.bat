@echo off
echo Adding changes...
git add .
echo Committing changes...
git commit -m "Add HR Project Tracking module, update GPS formatting to (GPS lat, lng), and enhance DB migration resilience"
echo Pushing to GitHub...
git push origin main --verbose
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Push failed! Check your internet and GitHub credentials.
    pause
    exit /b %ERRORLEVEL%
)
echo Done!
pause
