<#
.SYNOPSIS
    Builds the golden Windows GPU worker image for one app release (PF6).

.DESCRIPTION
    Run as Administrator on a fresh build machine of the class's instance type, at each app release:
      1. bootstrap.ps1 -ImageOnly: driver, Python, the release's Shipping build, the wrapper, the
         low-privilege account and the firewall rule; no credential;
      2. a first-boot script (C:\TruebexWorker\first-boot.ps1, run once by a SYSTEM startup task)
         that reads the worker's settings from the provider's user data and runs bootstrap.ps1 with
         them (token, worker id, kinds), so every machine started from the image registers itself;
      3. sysprep /generalize /oobe /shutdown, after which the provider's snapshot of the disk is the
         image (-Provider names how; until GD3 picks the provider, 'none' prints the manual step).
    Machines are re-imaged weekly and on every release, so a worker never runs an older app than the
    log it is handed (doc_version_max keeps older images off newer logs in between).

    User data format (provider metadata, plain text):
        TRUEBEX_API=https://api.truebex.com
        TRUEBEX_TOKEN=tbx_wrk_...
        TRUEBEX_WORKER_ID=gpu-eu-01
        TRUEBEX_KINDS=panorama,tiles,pack

.EXAMPLE
    .\build-image.ps1 -Channel stable -DriverUrl https://.../data-center-driver.exe
#>
[CmdletBinding()]
param(
    [ValidateSet('stable', 'beta')][string]$Channel = 'stable',
    [string]$Api = 'https://api.truebex.com',
    [string]$DriverUrl = '',
    # GD3 names the provider; its metadata URL feeds the first boot.
    [ValidateSet('none')][string]$Provider = 'none',
    [string]$UserDataUrl = 'http://169.254.169.254/latest/user-data',
    [switch]$NoSysprep
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$InstallDir = 'C:\TruebexWorker'

& (Join-Path $here 'bootstrap.ps1') -Api $Api -Channel $Channel -DriverUrl $DriverUrl -InstallDir $InstallDir -ImageOnly
Copy-Item -Force (Join-Path $here 'bootstrap.ps1') (Join-Path $InstallDir 'bootstrap.ps1')
New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir 'worker') | Out-Null
Copy-Item -Force (Join-Path (Split-Path -Parent (Split-Path -Parent $here)) 'worker\truebex_worker.py') (Join-Path $InstallDir 'worker\truebex_worker.py')

# The first boot: settings from the provider's user data, then a normal bootstrap.
$firstBoot = @"
`$ErrorActionPreference = 'Stop'
`$data = (Invoke-WebRequest -Uri '$UserDataUrl' -UseBasicParsing -TimeoutSec 10).Content
`$cfg = @{}
foreach (`$line in (`$data -split "``n")) { if (`$line -match '^\s*(TRUEBEX_\w+)=(.*)$') { `$cfg[`$Matches[1]] = `$Matches[2].Trim() } }
`$kinds = (`$cfg['TRUEBEX_KINDS'] -split ',') | Where-Object { `$_ }
& '$InstallDir\bootstrap.ps1' -Api `$cfg['TRUEBEX_API'] -Token `$cfg['TRUEBEX_TOKEN'] -WorkerId `$cfg['TRUEBEX_WORKER_ID'] -Kinds `$kinds -InstallDir '$InstallDir' -SkipApp
Unregister-ScheduledTask -TaskName 'Truebex worker first boot' -Confirm:`$false
"@
[IO.File]::WriteAllText((Join-Path $InstallDir 'first-boot.ps1'), $firstBoot)
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$InstallDir\first-boot.ps1`""
Register-ScheduledTask -TaskName 'Truebex worker first boot' -Action $action -Trigger (New-ScheduledTaskTrigger -AtStartup) `
    -User 'SYSTEM' -RunLevel Highest -Force | Out-Null

if ($NoSysprep) {
    Write-Host 'image prepared; sysprep skipped (-NoSysprep)'
    return
}
switch ($Provider) {
    'none' {
        Write-Host 'Next: sysprep runs and shuts the machine down. Then snapshot its disk in the provider console'
        Write-Host 'and name the image truebex-worker-<release>; GD3 replaces this step with the provider API.'
    }
}
& "$env:WINDIR\System32\Sysprep\sysprep.exe" /generalize /oobe /shutdown /quiet
