@echo off
REM Ensure we're on master branch first
git checkout master >nul 2>&1

echo ========================================
echo Building site on master branch...
echo ========================================
call npm run build

if errorlevel 1 (
    echo Build failed! Exiting...
    pause
    exit /b 1
)

REM Check if out folder exists
if not exist out (
    echo ERROR: Build completed but out folder not found!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Switching to gh-pages branch...
echo ========================================
git checkout gh-pages

if errorlevel 1 (
    echo Failed to switch to gh-pages branch!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Cleaning gh-pages branch (keeping only .git)...
echo ========================================
REM Remove all files and folders except .git
for /f "delims=" %%i in ('dir /b /a-d 2^>nul ^| findstr /v /i "^\.git"') do del /f /q "%%i" 2>nul
for /d %%i in (*) do @if /i not "%%~ni"==".git" rd /s /q "%%i" 2>nul

echo.
echo ========================================
echo Copying out folder contents to root...
echo ========================================
if exist out (
    xcopy /E /I /Y /H out\* . >nul 2>&1
    if errorlevel 1 (
        echo Warning: Some files may not have been copied
    )
    
    echo Removing out folder...
    rmdir /s /q out 2>nul
) else (
    echo ERROR: out folder not found! Make sure build completed successfully.
    git checkout master
    pause
    exit /b 1
)

echo.
echo ========================================
echo Creating .nojekyll file...
echo ========================================
echo. > .nojekyll

echo.
echo ========================================
echo Staging all changes...
echo ========================================
git add -A

echo.
echo ========================================
echo Committing changes...
echo ========================================
git commit -m "Deploy: Update site %date% %time%"

echo.
echo ========================================
echo Pushing to GitHub...
echo ========================================
git push origin gh-pages --force

if errorlevel 1 (
    echo Push failed! Check your git configuration.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Switching back to master branch...
echo ========================================
git checkout master

echo.
echo ========================================
echo Deployment complete!
echo ========================================
echo Your site will update on GitHub Pages in 1-2 minutes.
echo.
pause
