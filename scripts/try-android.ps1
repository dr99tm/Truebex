<#
.SYNOPSIS
    PF10 local trial: the Android app on a phone (USB) or the emulator, against the local API of
    scripts\try-mobile.ps1.

.DESCRIPTION
    1. Run scripts\try-mobile.ps1 -NoBuild in another terminal first: the API on :8000, a render worker
       and the demo House (alex@example.com and sam@example.com, password password123).
    2. This script builds the debug APK against http://127.0.0.1:8000, installs it on the device adb
       sees (-Device picks one), allows its notifications, routes the phone's 127.0.0.1:8000 through
       `adb reverse` to a relay on this PC (:8731 -> :8000) and opens the app.
    3. The relay then runs in this window. The USB tunnel ignores airplane mode, so to take the phone
       offline for the API: airplane mode on the phone AND Ctrl+C here. To bring it back:
       scripts\try-android.ps1 -RelayOnly, then airplane mode off.
    -SkipBuild reinstalls the last APK; -RelayOnly only restarts the relay (and the adb reverse).
#>
[CmdletBinding()]
param([string]$Device = '', [switch]$SkipBuild, [switch]$RelayOnly)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$adb = (Get-Command adb -ErrorAction SilentlyContinue).Source
if (-not $adb) { $adb = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe' }
if (-not (Test-Path $adb)) { throw 'adb was not found: install the Android SDK platform-tools (GD4).' }
$devices = @(& $adb devices | Select-Object -Skip 1 | Where-Object { $_ -match '\tdevice$' } | ForEach-Object { ($_ -split "`t")[0] })
if (-not $Device) {
    if (-not $devices) { throw 'No phone or emulator: connect one with USB debugging on (adb devices).' }
    $Device = $devices[0]
}
function Adb { & $adb -s $Device @args; if ($LASTEXITCODE -ne 0) { throw "adb $args failed" } }

if (-not $RelayOnly) {
    try { $null = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/health' -TimeoutSec 3 }
    catch { Write-Host 'Note: no API on :8000 yet. Start scripts\try-mobile.ps1 -NoBuild in another terminal.' }
    $apk = Join-Path $Root 'mobile\android\build\app\outputs\flutter-apk\app-debug.apk'
    if (-not $SkipBuild) {
        & node scripts/build-mobile-viewer.mjs
        if ($LASTEXITCODE -ne 0) { throw 'viewer bundle failed' }
        Push-Location (Join-Path $Root 'mobile\android')
        try {
            & flutter pub get | Out-Null
            & flutter build apk --debug --dart-define=TRUEBEX_API=http://127.0.0.1:8000
            if ($LASTEXITCODE -ne 0) { throw 'flutter build apk failed' }
        } finally { Pop-Location }
    }
    Write-Host "=== installing on $Device ==="
    Adb install -r $apk
    Adb shell pm grant com.truebex.app android.permission.POST_NOTIFICATIONS
}

Adb reverse tcp:8000 tcp:8731
if (-not $RelayOnly) { Adb shell am start -n com.truebex.app/.MainActivity }
$setup = Join-Path $Root 'server\try-mobile\setup.txt'
if (Test-Path $setup) {
    $token = (Select-String -Path $setup -Pattern 'tbx_dev_[A-Za-z0-9_-]+' | Select-Object -First 1).Matches.Value
    $project = (Select-String -Path $setup -Pattern 'project id: ([0-9a-f]{32})' | Select-Object -First 1).Matches.Groups[1].Value
    if ($token -and $project) {
        Write-Host ''
        Write-Host "Sam's desktop edit of the kitchen's west wall (for the conflict step), in another terminal:"
        Write-Host "  cd server; .venv\Scripts\python.exe scripts\demo_mobile.py --token $token move --project $project --entity 0199c6a2e00070018000000000000004"
    }
}
Write-Host ''
& py -3.12 (Join-Path $PSScriptRoot 'android_relay.py') 8731 8000
