@echo off
set TARGET_DIR=X:\Truebex_site_files\Truebex

echo ========================================
echo Building site...
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
echo Copying files to target directory...
echo ========================================
echo Target: %TARGET_DIR%

REM Create target directory if it doesn't exist
if not exist "%TARGET_DIR%" (
    mkdir "%TARGET_DIR%"
    echo Created target directory
)

REM Copy all files from out to target directory
xcopy /E /I /Y /H out\* "%TARGET_DIR%\" >nul 2>&1

if errorlevel 1 (
    echo Warning: Some files may not have been copied
) else (
    echo Files copied successfully!
)

echo.
echo ========================================
echo Build complete!
echo ========================================
echo Built files are in: %TARGET_DIR%
echo.
pause
