<#
.SYNOPSIS
    PF9 local trial: the API on :8000 with its own database, a render worker with the stand-in app, a shared
    "House" for the phone, the marketplace fixture, and out/ built against this API.

.DESCRIPTION
    Everything lives in server\try-mobile\ (gitignored): the SQLite database, storage, worker files and logs.
    Licensing uses the contract fixtures' TEST key (worthless outside tests); mail goes to the API console.
    Accounts: alex@example.com (the owner, signs in on the phone) and sam@example.com (an editor, the desktop's
    stand-in), both with password password123. The script keeps the API and the worker running until Ctrl+C.
    Then serve the site in another terminal: scripts\autopilot-serve.ps1 (port 3100 + the task number).

    -Reset starts from an empty database; -NoBuild keeps out/ as it is (rebuild after -Reset is not needed).
#>
[CmdletBinding()]
param([switch]$Reset, [switch]$NoBuild)
$ErrorActionPreference = 'Stop'
$Worktree = (Get-Location).Path
if ($env:AUTOPILOT_WORKTREE) { $Worktree = $env:AUTOPILOT_WORKTREE }
Set-Location $Worktree
$Server = Join-Path $Worktree 'server'
$Py = Join-Path $Server '.venv\Scripts\python.exe'
$State = Join-Path $Server 'try-mobile'
if ($Reset -and (Test-Path $State)) { Remove-Item -Recurse -Force $State }
New-Item -ItemType Directory -Force (Join-Path $State 'work') | Out-Null
$StateUri = ($State -replace '\\', '/')
$n = 0
if ($env:AUTOPILOT_TASK_ID -match '^T(\d+)$') { $n = [int]$Matches[1] }
$SitePort = 3100 + $n

# Settings for this process and its children (the API, the scripts, the worker).
$secretFile = Join-Path $State 'secret.txt'
if (-not (Test-Path $secretFile)) { -join ((1..48) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) }) | Set-Content -Encoding ascii $secretFile }
$key = Get-Content (Join-Path $Server 'tests\contracts\licence\keys.json') -Raw | ConvertFrom-Json
$env:DATABASE_URL = "sqlite:///$StateUri/try.db"
$env:SECRET_KEY = (Get-Content $secretFile -Raw).Trim()
$env:STORAGE_BACKEND = 'local'
$env:STORAGE_DIR = "$StateUri/storage"
$env:API_URL = 'http://127.0.0.1:8000'
$env:SITE_URL = "http://127.0.0.1:$SitePort"
$origins = @("http://127.0.0.1:$SitePort", "http://localhost:$SitePort", 'http://127.0.0.1:3100', 'http://localhost:3100') | Select-Object -Unique
$env:CORS_ORIGINS = $origins -join ','
$env:MAIL_BACKEND = 'console'
$env:BACKGROUND_TASKS = 'inline'
$env:LICENCE_SIGNING_KEY = $key.keys[0].private_key
$env:LICENCE_KEY_ID = $key.keys[0].kid

Write-Host "=== API on http://127.0.0.1:8000 (log: server\try-mobile\api.log) ==="
$api = Start-Process -FilePath $Py -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000' `
    -WorkingDirectory $Server -RedirectStandardOutput (Join-Path $State 'api.out.log') -RedirectStandardError (Join-Path $State 'api.log') -PassThru -WindowStyle Hidden
$worker = $null
try {
    $up = $false
    foreach ($i in 1..60) {
        try { if ((Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/health' -TimeoutSec 2).StatusCode -eq 200) { $up = $true; break } } catch {}
        Start-Sleep -Seconds 1
    }
    if (-not $up) { throw 'The API did not start: see server\try-mobile\api.log (is port 8000 taken?)' }

    Write-Host '=== House for the phone (scripts\demo_mobile.py setup) ==='
    Push-Location $Server
    try {
        & $Py scripts\demo_mobile.py setup --email alex@example.com --password password123 --editor-email sam@example.com --site "http://127.0.0.1:$SitePort" | Tee-Object -FilePath (Join-Path $State 'setup.txt')
        if ($LASTEXITCODE -ne 0) { throw 'demo_mobile.py setup failed' }
        Write-Host '=== Marketplace fixture (prices and swaps) ==='
        & $Py scripts\seed_market.py --fixture tests\fixtures\market | Out-Null
        & $Py scripts\make_admin.py alex@example.com | Out-Null
    } finally { Pop-Location }

    # A worker token for this database (Admin -> Render does the same in the dashboard).
    $tomlPath = Join-Path $State 'worker.toml'
    $session = (Invoke-RestMethod -Method Post 'http://127.0.0.1:8000/auth/login' -ContentType 'application/json' -Body '{"email":"alex@example.com","password":"password123"}').access_token
    $workers = Invoke-RestMethod 'http://127.0.0.1:8000/admin/render' -Headers @{ Authorization = "Bearer $session" }
    $saved = if (Test-Path $tomlPath) { (Select-String -Path $tomlPath -Pattern '^worker_id = "(.+)"$').Matches.Groups[1].Value } else { '' }
    $active = @($workers.workers | Where-Object { $_.worker_id -eq $saved -and -not $_.revoked_at })
    if (-not $active) {
        $name = 'pc-try-' + (Get-Date -Format 'MMddHHmmss')
        $body = '{"name":"' + $name + '","kinds":["panorama","tiles"],"class":"gpu-std"}'
        $issued = Invoke-RestMethod -Method Post 'http://127.0.0.1:8000/admin/workers' -ContentType 'application/json' -Headers @{ Authorization = "Bearer $session" } -Body $body
        $fake = (Join-Path $Worktree 'worker\tests\fake_truebex.py') -replace '\\', '/'
        @"
api = "http://127.0.0.1:8000"
token = "$($issued.token)"
worker_id = "$name"
kinds = ["panorama", "tiles"]
class = "gpu-std"
app = "$fake"
app_version = "0.0.0-fake"
doc_version_max = 38
work_dir = "$StateUri/work"
keep_work = false
heartbeat_s = 30
job_timeout_s = 600
wait_s = 5
face_px = 1024
tile_px = 512
jpeg_quality = 85
"@ | Set-Content -Encoding ascii $tomlPath
    }
    Write-Host '=== Render worker with the stand-in app (log: server\try-mobile\worker.log) ==='
    $worker = Start-Process -FilePath $Py -ArgumentList (Join-Path $Worktree 'worker\truebex_worker.py'), '--config', $tomlPath `
        -WorkingDirectory $Worktree -RedirectStandardOutput (Join-Path $State 'worker.log') -RedirectStandardError (Join-Path $State 'worker.err.log') -PassThru -WindowStyle Hidden

    if (-not $NoBuild) {
        Write-Host '=== Building out/ against http://127.0.0.1:8000 (a few minutes) ==='
        $env:NEXT_PUBLIC_AUTH_URL = 'http://127.0.0.1:8000'
        if (Test-Path (Join-Path $Worktree 'out')) { Remove-Item -Recurse -Force (Join-Path $Worktree 'out') }
        & npm run build | Out-Host
        if ($LASTEXITCODE -ne 0) { throw 'npm run build failed' }
    }

    Write-Host ''
    Write-Host 'Ready. In another terminal: powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1'
    Write-Host "Then open http://127.0.0.1:$SitePort/app/ and sign in as alex@example.com / password123."
    Get-Content (Join-Path $State 'setup.txt') | Where-Object { $_ -match 'project id|device token' } | ForEach-Object { Write-Host "  $_" }
    Write-Host 'The API and the worker run until Ctrl+C.'
    while (-not $api.HasExited) { Start-Sleep -Seconds 2 }
    Write-Host 'The API stopped: see server\try-mobile\api.log'
} finally {
    foreach ($p in @($worker, $api)) { if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } }
}
