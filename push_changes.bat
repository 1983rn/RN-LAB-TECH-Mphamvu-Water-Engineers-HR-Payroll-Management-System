@echo off
echo Adding changes...
git add .
echo Committing changes...
git commit -m "Fix Internal Server Error on Quotation page: Added automated DB migrations for all departments and template safety checks"
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
