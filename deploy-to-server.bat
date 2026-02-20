@echo off
set SERVER_DIR=X:\Truebex_site_files\Truebex
set BACKUP_DIR=X:\Truebex_site_files\Truebex_backup
set WORKFLOW_FILE=%SERVER_DIR%\.github\workflows\static.yml

echo ========================================
echo Building project...
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
echo Creating backup of server files...
echo ========================================

REM Create backup directory with timestamp
set TIMESTAMP=%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set BACKUP_DIR_TIMESTAMP=%BACKUP_DIR%_%TIMESTAMP%

if exist "%SERVER_DIR%" (
    if not exist "%BACKUP_DIR_TIMESTAMP%" mkdir "%BACKUP_DIR_TIMESTAMP%"
    echo Backing up to: %BACKUP_DIR_TIMESTAMP%
    xcopy /E /I /Y /H "%SERVER_DIR%\*" "%BACKUP_DIR_TIMESTAMP%\" >nul 2>&1
    echo Backup created successfully!
) else (
    echo Server directory not found, creating it...
    mkdir "%SERVER_DIR%"
)

echo.
echo ========================================
echo Saving workflow file...
echo ========================================

REM Save the workflow file if it exists (before cleaning)
set WORKFLOW_BACKUP=%TEMP%\static.yml.backup
if exist "%WORKFLOW_FILE%" (
    copy /Y "%WORKFLOW_FILE%" "%WORKFLOW_BACKUP%" >nul 2>&1
    echo Workflow file backed up
)

echo.
echo ========================================
echo Cleaning server directory...
echo ========================================

REM Remove all files except .git and .github folders
cd /d "%SERVER_DIR%"
for /f "delims=" %%i in ('dir /b /a-d 2^>nul ^| findstr /v /i "^\.git"') do del /f /q "%%i" 2>nul
for /d %%i in (*) do @if /i not "%%~ni"==".git" if /i not "%%~ni"==".github" rd /s /q "%%i" 2>nul

cd /d "%~dp0"

echo.
echo ========================================
echo Copying build files to server...
echo ========================================

REM Copy all files from out to server directory (including hidden files and SVG)
xcopy /E /I /Y /H /K out\* "%SERVER_DIR%\" >nul 2>&1

REM Force copy SVG files explicitly
for /r out %%f in (*.svg) do (
    set "relpath=%%f"
    setlocal enabledelayedexpansion
    set "relpath=!relpath:%CD%\out\=!"
    if not exist "%SERVER_DIR%\!relpath!" (
        copy /Y "%%f" "%SERVER_DIR%\!relpath!" >nul 2>&1
    )
    endlocal
)

if errorlevel 1 (
    echo Warning: Some files may not have been copied
) else (
    echo Files copied successfully!
)

echo.
echo ========================================
echo Restoring workflow file...
echo ========================================

REM Ensure .github/workflows directory exists
if not exist "%SERVER_DIR%\.github\workflows" (
    mkdir "%SERVER_DIR%\.github\workflows"
)

REM Restore the workflow file from backup and touch it to update timestamp
if exist "%WORKFLOW_BACKUP%" (
    copy /Y "%WORKFLOW_BACKUP%" "%WORKFLOW_FILE%" >nul 2>&1
    REM Touch the file to update its timestamp
    copy /B "%WORKFLOW_FILE%" +,, "%WORKFLOW_FILE%" >nul 2>&1
    del /Q "%WORKFLOW_BACKUP%" >nul 2>&1
    echo Workflow file restored and timestamp updated
) else (
    REM If workflow file doesn't exist, create the one from the server directory
    echo Creating workflow file from template...
    (
        echo # Simple workflow for deploying static content to GitHub Pages
        echo name: Deploy static content to Pages
        echo.
        echo on:
        echo   # Runs on pushes targeting the default branch
        echo   push:
        echo     branches: ["main"]
        echo.
        echo   # Allows you to run this workflow manually from the Actions tab
        echo   workflow_dispatch:
        echo.
        echo # Sets permissions of the GITHUB_TOKEN to allow deployment to GitHub Pages
        echo permissions:
        echo   contents: read
        echo   pages: write
        echo   id-token: write
        echo.
        echo # Allow only one concurrent deployment, skipping runs queued between the run in-progress and latest queued.
        echo # However, do NOT cancel in-progress runs as we want to allow these production deployments to complete.
        echo concurrency:
        echo   group: "pages"
        echo   cancel-in-progress: false
        echo.
        echo jobs:
        echo   # Single deploy job since we're just deploying
        echo   deploy:
        echo     environment:
        echo       name: github-pages
        echo       url: ${{ steps.deployment.outputs.page_url }}
        echo     runs-on: ubuntu-latest
        echo     steps:
        echo       - name: Checkout
        echo         uses: actions/checkout@v4
        echo       - name: Setup Pages
        echo         uses: actions/configure-pages@v5
        echo       - name: Upload artifact
        echo         uses: actions/upload-pages-artifact@v3
        echo         with:
        echo           # Upload entire repository
        echo           path: '.'
        echo       - name: Deploy to GitHub Pages
        echo         id: deployment
        echo         uses: actions/deploy-pages@v4
    ) > "%WORKFLOW_FILE%"
    echo Workflow file created
)

echo.
echo ========================================
echo Updating file timestamps...
echo ========================================

REM Touch SVG and YAML files to update their timestamps
cd /d "%SERVER_DIR%"
for /r %%f in (*.svg *.yml *.yaml) do (
    copy /B "%%f" +,, "%%f" >nul 2>&1
)

echo.
echo ========================================
echo Committing and pushing to server...
echo ========================================

REM Check if it's a git repository
if not exist ".git" (
    echo ERROR: Server directory is not a git repository!
    echo Please initialize git first: git init
    cd /d "%~dp0"
    pause
    exit /b 1
)

REM Force add all changes (including SVG and YAML files)
git add -A --force

REM Explicitly add SVG and YAML files
for /r %%f in (*.svg *.yml *.yaml) do (
    git add -f "%%f" >nul 2>&1
)

REM Check if there are any changes
git status --short >nul 2>&1
if errorlevel 1 (
    echo No changes detected, forcing commit...
    REM Force commit even if Git thinks nothing changed
    git commit --allow-empty -m "Deploy: Update site %date% %time%"
    echo Empty commit created to update timestamps
) else (
    REM Commit normally
    git commit -m "Deploy: Update site %date% %time%"
    
    if errorlevel 1 (
        echo Commit failed, trying with --allow-empty...
        git commit --allow-empty -m "Deploy: Update site %date% %time%"
    )
    
    echo Changes committed
)

REM Push to server
echo Pushing to remote repository...
git push

if errorlevel 1 (
    echo Push failed! Check your git configuration.
    echo Make sure remote is configured: git remote add origin YOUR_REPO_URL
    cd /d "%~dp0"
    pause
    exit /b 1
)

cd /d "%~dp0"

echo.
echo ========================================
echo Deployment complete!
echo ========================================
echo Backup saved to: %BACKUP_DIR_TIMESTAMP%
echo Server files updated in: %SERVER_DIR%
echo.
pause
