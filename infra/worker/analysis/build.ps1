<#
.SYNOPSIS
    Build an analysis runner image (PF11): truebex-analysis-<kind>:<tag>.

.DESCRIPTION
    The build context is a temporary folder holding the runner package
    (server/app/analysis/runners), the shared entrypoint run.sh (with LF line
    ends) and the kind's Dockerfile. Needs Docker (Docker Desktop with Linux
    containers on Windows).

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File infra\worker\analysis\build.ps1 -Kind wind
    powershell -NoProfile -ExecutionPolicy Bypass -File infra\worker\analysis\build.ps1 -Kind energy -BuildArg "ENERGYPLUS_SHA256=<sha>"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('wind', 'energy', 'acoustics', 'texture', 'airflow')][string]$Kind,
    [string]$Tag = '1',
    [string[]]$BuildArg = @()
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here '..\..\..')).Path
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host 'docker is not on PATH: install Docker Desktop (Linux containers), start it, and try again.'
    exit 1
}
$ctx = Join-Path ([System.IO.Path]::GetTempPath()) ('truebex-analysis-' + $Kind + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Force -Path $ctx | Out-Null
try {
    Copy-Item -Recurse -Path (Join-Path $repo 'server\app\analysis\runners') -Destination (Join-Path $ctx 'runners')
    Get-ChildItem -Path (Join-Path $ctx 'runners') -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
    $runSh = [System.IO.File]::ReadAllText((Join-Path $here 'run.sh')) -replace "`r`n", "`n"
    [System.IO.File]::WriteAllText((Join-Path $ctx 'run.sh'), $runSh, (New-Object System.Text.UTF8Encoding($false)))
    Copy-Item -Path (Join-Path $here "$Kind\Dockerfile") -Destination (Join-Path $ctx 'Dockerfile')
    $image = "truebex-analysis-${Kind}:$Tag"
    $dockerArgs = @('build', '-t', $image, '--build-arg', "TRUEBEX_IMAGE=$image")
    foreach ($a in $BuildArg) { $dockerArgs += @('--build-arg', $a) }
    $dockerArgs += $ctx
    Write-Host "building $image"
    & docker @dockerArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "docker build failed ($LASTEXITCODE)"
        exit $LASTEXITCODE
    }
    Write-Host "built $image"
}
finally {
    Remove-Item -Recurse -Force -Path $ctx -ErrorAction SilentlyContinue
}
