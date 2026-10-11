# Build truebex-analysis-energy (PF11): the shared ..\build.ps1 with -Kind energy.
#   powershell -NoProfile -ExecutionPolicy Bypass -File infra\worker\analysis\energy\build.ps1 -BuildArg "ENERGYPLUS_SHA256=<sha>"
param([string]$Tag = '1', [string[]]$BuildArg = @())
& (Join-Path $PSScriptRoot '..\build.ps1') -Kind energy -Tag $Tag -BuildArg $BuildArg
exit $LASTEXITCODE
