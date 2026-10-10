<#
.SYNOPSIS
    Turns a Windows machine with an NVIDIA GPU into a Truebex render worker (PF6).

.DESCRIPTION
    Run as Administrator on a fresh machine (a cloud GPU instance, or the owner's RTX PC for the static
    pool). In order:
      1. the NVIDIA driver (-DriverUrl: the data-centre driver GD3 picks; skipped when nvidia-smi works),
      2. Python 3.12 for all users (the worker wrapper needs nothing else),
      3. the Shipping build of the newest release on -Channel from the platform's release feed
         (licence-api 5.13 / 5.14), its SHA-256 checked,
      4. the wrapper (worker\truebex_worker.py) and its worker.toml in -InstallDir,
      5. a low-privilege local account 'truebex-worker' (no admin rights) that owns only -InstallDir,
      6. a scheduled task that starts the wrapper at boot as that account and restarts it after a crash,
      7. an outbound firewall rule that blocks Truebex.exe from the network: the app renders project
         content, so only the wrapper talks to the API, the bucket and the CDN. Restrict the machine's
         egress to those hosts in the provider's firewall too (GD3).
    -ImageOnly (used by build-image.ps1) stops before the token and the task: a golden image carries no
    credential; the first boot writes worker.toml from the provider's user data.

.EXAMPLE
    .\bootstrap.ps1 -Token tbx_wrk_... -WorkerId pc-rtx
.EXAMPLE
    .\bootstrap.ps1 -Api http://127.0.0.1:8000 -Token tbx_wrk_... -WorkerId pc-rtx -SkipApp -App 'C:\Truebex\Truebex.exe'
#>
[CmdletBinding()]
param(
    [string]$Api = 'https://api.truebex.com',
    [string]$Token = '',
    [string]$WorkerId = $env:COMPUTERNAME.ToLowerInvariant(),
    [string[]]$Kinds = @('panorama', 'tiles', 'pack'),
    [string]$Class = 'gpu-std',
    [ValidateSet('stable', 'beta')][string]$Channel = 'stable',
    [string]$DriverUrl = '',
    [string]$PythonUrl = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe',
    # The installer's silent switches (LC2 decides the installer; these are Inno Setup's).
    [string]$InstallerArgs = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART',
    [string]$App = 'C:\Program Files\Truebex\Truebex.exe',
    [string]$InstallDir = 'C:\TruebexWorker',
    [int]$DocVersionMax = 38,
    [switch]$SkipApp,
    [switch]$ImageOnly
)
$ErrorActionPreference = 'Stop'
# Beside this script in an image (C:\TruebexWorker\worker\), else the repository's worker\.
$Wrapper = Join-Path $PSScriptRoot 'worker\truebex_worker.py'
if (-not (Test-Path $Wrapper)) {
    $Wrapper = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'worker\truebex_worker.py'
}
$TaskName = 'Truebex render worker'
$Account = 'truebex-worker'

function Step($text) { Write-Host "=== $text" }

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run bootstrap.ps1 as Administrator.'
}
if (-not $ImageOnly -and -not $Token.StartsWith('tbx_wrk_')) {
    throw 'Pass -Token tbx_wrk_... (Admin -> Render -> Issue worker token), or -ImageOnly.'
}
New-Item -ItemType Directory -Force -Path $InstallDir, (Join-Path $InstallDir 'jobs'), (Join-Path $InstallDir 'downloads') | Out-Null
$downloads = Join-Path $InstallDir 'downloads'

# 1. NVIDIA driver
Step 'NVIDIA driver'
$smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($smi) {
    & $smi.Source --query-gpu=name,driver_version,memory.total --format=csv,noheader
} elseif ($DriverUrl) {
    $driver = Join-Path $downloads 'nvidia-driver.exe'
    Invoke-WebRequest -Uri $DriverUrl -OutFile $driver -UseBasicParsing
    $p = Start-Process -FilePath $driver -ArgumentList '-s', '-noreboot', '-clean' -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "The NVIDIA driver installer exited $($p.ExitCode)." }
} else {
    Write-Warning 'No nvidia-smi and no -DriverUrl: install the GPU driver before the first job.'
}

# 2. Python 3.12
Step 'Python 3.12'
$py = $null
try { $py = (& py -3.12 -c 'import sys; print(sys.executable)' 2>$null) } catch { $py = $null }
if (-not $py) {
    $installer = Join-Path $downloads 'python-3.12.exe'
    Invoke-WebRequest -Uri $PythonUrl -OutFile $installer -UseBasicParsing
    $p = Start-Process -FilePath $installer -ArgumentList '/quiet', 'InstallAllUsers=1', 'PrependPath=1', 'Include_test=0', 'Include_launcher=1' -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "The Python installer exited $($p.ExitCode)." }
    $py = 'C:\Program Files\Python312\python.exe'
}
$py = "$py".Trim()
Write-Host "python: $py"

# 3. The Shipping build of the newest release
if (-not $SkipApp) {
    Step "Truebex ($Channel)"
    $headers = @{ 'X-Truebex-Contract' = 'licence-api/1.0' }
    $feed = Invoke-RestMethod -Uri "$Api/releases/feed?channel=$Channel&platform=win64" -Headers $headers
    if (-not $feed.latest) { throw "The release feed has no $Channel release." }
    $headers['Accept'] = 'application/json'
    $dl = Invoke-RestMethod -Uri "$Api/releases/$($feed.latest)/download?platform=win64" -Headers $headers
    $setup = Join-Path $downloads "Truebex-Setup-$($feed.latest).exe"
    Invoke-WebRequest -Uri $dl.url -OutFile $setup -UseBasicParsing
    $hash = (Get-FileHash -Algorithm SHA256 -Path $setup).Hash.ToLowerInvariant()
    if ($hash -ne $dl.sha256) { throw "The installer's SHA-256 is $hash, the feed says $($dl.sha256)." }
    $p = Start-Process -FilePath $setup -ArgumentList $InstallerArgs -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "The Truebex installer exited $($p.ExitCode)." }
    Write-Host "installed Truebex $($feed.latest)"
    $appVersion = $feed.latest
    [IO.File]::WriteAllText((Join-Path $InstallDir 'app-version.txt'), $appVersion)
} elseif (Test-Path (Join-Path $InstallDir 'app-version.txt')) {
    $appVersion = (Get-Content (Join-Path $InstallDir 'app-version.txt') -Raw).Trim()
} else {
    $appVersion = '0.0.0'
}
if (-not (Test-Path $App)) { Write-Warning "$App is missing: set app in worker.toml." }

# 4. The wrapper and its settings
Step 'worker wrapper'
Copy-Item -Force $Wrapper (Join-Path $InstallDir 'truebex_worker.py')
$toml = Join-Path $InstallDir 'worker.toml'
$kindsToml = ($Kinds | ForEach-Object { '"' + $_ + '"' }) -join ', '
$lines = @(
    "api = `"$Api`"",
    "token = `"$Token`"",
    "worker_id = `"$WorkerId`"",
    "kinds = [$kindsToml]",
    "class = `"$Class`"",
    "app = '$App'",
    "app_version = `"$appVersion`"",
    "doc_version_max = $DocVersionMax",
    "work_dir = '$(Join-Path $InstallDir 'jobs')'",
    'heartbeat_s = 30',
    'job_timeout_s = 3600',
    'wait_s = 20'
)
if (-not $ImageOnly) {
    [IO.File]::WriteAllText($toml, ($lines -join "`n") + "`n")
}

# 5. A low-privilege account that owns only the worker's folder
Step "account $Account"
$bytes = New-Object byte[] 24
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$password = [Convert]::ToBase64String($bytes) + 'aA1!'
$secure = ConvertTo-SecureString $password -AsPlainText -Force
if (Get-LocalUser -Name $Account -ErrorAction SilentlyContinue) {
    Set-LocalUser -Name $Account -Password $secure
} else {
    New-LocalUser -Name $Account -Password $secure -PasswordNeverExpires -AccountNeverExpires `
        -Description 'Runs the Truebex render worker (PF6)' | Out-Null
}
& icacls $InstallDir /inheritance:r /grant:r "Administrators:(OI)(CI)F" "SYSTEM:(OI)(CI)F" "${Account}:(OI)(CI)M" | Out-Null
if (Test-Path $toml) { & icacls $toml /inheritance:r /grant:r "Administrators:F" "SYSTEM:F" "${Account}:R" | Out-Null }

# 7. The app never reaches the network itself
Step 'firewall'
if (-not (Get-NetFirewallRule -DisplayName 'Truebex render: app offline' -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName 'Truebex render: app offline' -Direction Outbound -Program $App -Action Block | Out-Null
}

if ($ImageOnly) {
    Write-Host 'image prepared: no token, no task (the first boot adds them)'
    return
}

# 6. Start at boot, restart after a crash
Step "task '$TaskName'"
$action = New-ScheduledTaskAction -Execute $py -Argument "`"$(Join-Path $InstallDir 'truebex_worker.py')`" --config `"$toml`"" -WorkingDirectory $InstallDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -User $Account -Password $password -RunLevel Limited -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "worker $WorkerId started; Admin -> Render shows its heartbeat within a minute"
