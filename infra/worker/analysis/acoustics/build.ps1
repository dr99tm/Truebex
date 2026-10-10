# Build truebex-analysis-acoustics (PF11): the shared ..\build.ps1 with -Kind acoustics.
#   powershell -NoProfile -ExecutionPolicy Bypass -File infra\worker\analysis\acoustics\build.ps1 [-Tag 1]
param([string]$Tag = '1', [string[]]$BuildArg = @())
& (Join-Path $PSScriptRoot '..\build.ps1') -Kind acoustics -Tag $Tag -BuildArg $BuildArg
exit $LASTEXITCODE
