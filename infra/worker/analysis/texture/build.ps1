# Build truebex-analysis-texture (PF11): the shared ..\build.ps1 with -Kind texture.
#   powershell -NoProfile -ExecutionPolicy Bypass -File infra\worker\analysis\texture\build.ps1 -BuildArg "TEXTURE_MODEL=<model id>"
param([string]$Tag = '1', [string[]]$BuildArg = @())
& (Join-Path $PSScriptRoot '..\build.ps1') -Kind texture -Tag $Tag -BuildArg $BuildArg
exit $LASTEXITCODE
