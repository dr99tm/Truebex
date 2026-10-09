<#
.SYNOPSIS
    Claude Autopilot's setupCommand for the Truebex platform repo: run ONCE in a fresh task worktree.

.DESCRIPTION
    Copies .env.local from the main checkout (it is gitignored and holds the production URLs the
    static export bakes in), installs node modules, and creates server\.venv with Python 3.12
    (the pinned server dependencies do not install on 3.14).
#>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

$Worktree = (Get-Location).Path
if ($env:AUTOPILOT_WORKTREE) { $Worktree = $env:AUTOPILOT_WORKTREE }
$Main = 'X:\Truebex'
Set-Location $Worktree

if (-not (Test-Path (Join-Path $Worktree '.env.local'))) {
    if (Test-Path (Join-Path $Main '.env.local')) {
        Copy-Item (Join-Path $Main '.env.local') (Join-Path $Worktree '.env.local')
        Write-Host "copied .env.local from $Main"
    } else {
        Copy-Item (Join-Path $Worktree '.env.example') (Join-Path $Worktree '.env.local')
        Write-Host "no .env.local in $Main -- copied .env.example"
    }
}

Write-Host "npm ci ..."
& npm ci --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw "npm ci failed ($LASTEXITCODE)" }

$venvPy = Join-Path $Worktree 'server\.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    Write-Host "creating server\.venv with Python 3.12 ..."
    Push-Location (Join-Path $Worktree 'server')
    try {
        & py -3.12 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "venv creation failed ($LASTEXITCODE)" }
        & .venv\Scripts\python.exe -m pip install -q -r requirements-dev.txt
        if ($LASTEXITCODE -ne 0) { throw "pip install failed ($LASTEXITCODE)" }
    } finally { Pop-Location }
}
Write-Host "setup done: $Worktree"
