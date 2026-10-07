@echo off
REM Expose the local API (localhost:8001) as https://api.truebex.com.
REM cloudflared isn't on PATH on this machine; it lives in the profile folder.
set CLOUDFLARED=%USERPROFILE%\.cloudflared\cloudflared.exe
if not exist "%CLOUDFLARED%" set CLOUDFLARED=cloudflared
"%CLOUDFLARED%" tunnel --config "%USERPROFILE%\.cloudflared\config.yml" run win-tunnel
pause
