@echo off
REM This script forces SVG and YAML files to be updated in Git
REM by touching them and ensuring they're committed

set SERVER_DIR=X:\Truebex_site_files\Truebex

cd /d "%SERVER_DIR%"

echo Updating timestamps for SVG and YAML files...

REM Touch all SVG files
for /r %%f in (*.svg) do (
    copy /B "%%f" +,, "%%f" >nul 2>&1
    git add -f "%%f"
)

REM Touch all YAML files
for /r %%f in (*.yml *.yaml) do (
    copy /B "%%f" +,, "%%f" >nul 2>&1
    git add -f "%%f"
)

REM Commit if there are changes
git status --short >nul 2>&1
if not errorlevel 1 (
    git commit -m "Update: Refresh SVG and YAML files %date% %time%"
    git push
    echo Files updated and pushed!
) else (
    echo No changes detected - files are identical
    echo Creating empty commit to update GitHub timestamps...
    git commit --allow-empty -m "Update: Refresh file timestamps %date% %time%"
    git push
    echo Empty commit pushed!
)

pause
