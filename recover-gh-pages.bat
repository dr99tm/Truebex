@echo off
echo ========================================
echo Recovering gh-pages branch...
echo ========================================

REM Remove git lock file
if exist ".git\index.lock" (
    del /f /q ".git\index.lock"
    echo Removed git lock file
)

REM Check if we're on gh-pages
git branch --show-current | findstr /i "gh-pages" >nul
if errorlevel 1 (
    echo Switching to gh-pages branch...
    git checkout gh-pages
)

REM Check if out folder exists
if not exist out (
    echo ERROR: out folder not found!
    echo Please run: git checkout master
    echo Then run: npm run build
    echo Then run this script again.
    pause
    exit /b 1
)

echo.
echo Copying files from out folder to root...
xcopy /E /I /Y /H out\* .

echo Creating .nojekyll file...
echo. > .nojekyll

echo.
echo Staging changes...
git add -A

echo.
echo Committing...
git commit -m "Recover: Restore files from out folder"

echo.
echo Pushing to GitHub...
git push origin gh-pages --force

echo.
echo ========================================
echo Recovery complete!
echo ========================================
pause
