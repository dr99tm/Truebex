# Build truebex-analysis-airflow (PF11c): the shared ..\build.ps1 with -Kind airflow.
#   powershell -NoProfile -ExecutionPolicy Bypass -File infra\worker\analysis\airflow\build.ps1 [-Tag 1]
param([string]$Tag = '1', [string[]]$BuildArg = @())
& (Join-Path $PSScriptRoot '..\build.ps1') -Kind airflow -Tag $Tag -BuildArg $BuildArg
exit $LASTEXITCODE
