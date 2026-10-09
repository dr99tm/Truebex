<#
.SYNOPSIS
    The verify gate for the Truebex platform repo under Claude Autopilot: lint, static build, server tests.

.DESCRIPTION
    Runs in the task worktree. Fails on the first red step. Never runs `next dev`.
    1. npm run lint            (eslint)
    2. npm run build           (Next.js static export to out/)
    3. pytest -q               (server/, in server\.venv)
    4. out/index.html exists and carries the API URL from .env.local
#>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Worktree = (Get-Location).Path
if ($env:AUTOPILOT_WORKTREE) { $Worktree = $env:AUTOPILOT_WORKTREE }
Set-Location $Worktree

function Step($name, [scriptblock]$body) {
    Write-Host "=== $name ==="
    & $body
    if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: $name ($LASTEXITCODE)"; exit 1 }
}

Step 'lint' { & npm run lint }
if (Test-Path (Join-Path $Worktree 'out')) { Remove-Item -Recurse -Force (Join-Path $Worktree 'out') }
Step 'build' { & npm run build }
Step 'server tests' {
    Push-Location (Join-Path $Worktree 'server')
    try { & .venv\Scripts\python.exe -m pytest -q } finally { Pop-Location }
}

$index = Join-Path $Worktree 'out\index.html'
if (-not (Test-Path $index)) { Write-Host 'FAIL: out/index.html missing'; exit 1 }
$envFile = Join-Path $Worktree '.env.local'
$apiUrl = ''
if (Test-Path $envFile) {
    $line = Get-Content $envFile | Where-Object { $_ -match '^NEXT_PUBLIC_AUTH_URL=' } | Select-Object -First 1
    if ($line) { $apiUrl = ($line -split '=', 2)[1].Trim() }
}
if ($apiUrl) {
    $hit = Get-ChildItem (Join-Path $Worktree 'out\_next') -Recurse -Filter *.js | Select-String -SimpleMatch $apiUrl -List | Select-Object -First 1
    if (-not $hit) { Write-Host "FAIL: no built chunk carries $apiUrl"; exit 1 }
}
Write-Host 'verify GREEN'
exit 0
