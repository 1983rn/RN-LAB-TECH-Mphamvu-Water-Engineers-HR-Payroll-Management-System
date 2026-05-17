@echo off
echo Adding changes...
git add .
echo Committing changes...
git commit -m "Update HR Project Tracking UI with clickable GPS coordinates and fix client project type dynamic dropdown"
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
