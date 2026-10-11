# Build truebex-analysis-wind (PF11): the shared ..\build.ps1 with -Kind wind.
#   powershell -NoProfile -ExecutionPolicy Bypass -File infra\worker\analysis\wind\build.ps1 [-Tag 1] [-BuildArg "K=V"]
param([string]$Tag = '1', [string[]]$BuildArg = @())
& (Join-Path $PSScriptRoot '..\build.ps1') -Kind wind -Tag $Tag -BuildArg $BuildArg
exit $LASTEXITCODE
