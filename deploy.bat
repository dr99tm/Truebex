@echo off
echo Building site...
call npm run build

echo Switching to gh-pages branch...
git checkout gh-pages

echo Cleaning old files...
for /f "delims=" %%i in ('dir /b /a-d ^| findstr /v /i "\.git"') do del /f /q "%%i"
for /d /r %%i in (*) do @if /i not "%%~ni"=="out" if /i not "%%~ni"==".git" rd /s /q "%%i" 2>nul

echo Moving out folder contents to root...
xcopy /E /I /Y /H out\* .
rmdir /s /q out 2>nul

echo Creating .nojekyll file...
echo. > .nojekyll

echo Staging changes...
git add .

echo Committing...
git commit -m "Deploy: Update site %date% %time%"

echo Pushing to GitHub...
git push origin gh-pages --force

echo Switching back to master...
git checkout master

echo.
echo Deployment complete! Site will update in 1-2 minutes.
pause
