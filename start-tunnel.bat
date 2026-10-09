@echo off
REM LOCAL USE ONLY since PF14: api.truebex.com points at the VM (infra/,
REM CUTOVER.md step 4 removed the tunnel's api ingress). Keep this only for
REM exposing a local test hostname, never api.truebex.com.
REM cloudflared isn't on PATH on this machine; it lives in the profile folder.
set CLOUDFLARED=%USERPROFILE%\.cloudflared\cloudflared.exe
if not exist "%CLOUDFLARED%" set CLOUDFLARED=cloudflared
"%CLOUDFLARED%" tunnel --config "%USERPROFILE%\.cloudflared\config.yml" run win-tunnel
pause
