<#
.SYNOPSIS
    The mobile gate (PF10): the Android app's analyzer, its tests and a debug APK.

.DESCRIPTION
    A separate gate, so scripts\autopilot-verify.ps1 never needs the Flutter SDK. Needs Flutter (stable),
    the Android SDK and a JDK 17 (GD4: store accounts and toolchains). Fails on the first red step.
    1. node scripts/build-mobile-viewer.mjs   PF9's viewer bundled into mobile/android/assets/viewer/
    2. flutter pub get
    3. flutter analyze
    4. flutter test                           unit and widget tests (they read server/tests/contracts/)
    5. flutter build apk --debug              mobile/android/build/app/outputs/flutter-apk/app-debug.apk

    -Api sets the API the APK talks to (default https://api.truebex.com). A local API on this PC reached
    over USB or from the emulator: -Api http://127.0.0.1:8000 with `adb reverse tcp:8000 tcp:8000`
    (scripts\try-android.ps1 does both). -GoogleServerClientId is the Web client id used as Credential
    Manager's server client id; without it the app offers e-mail and password only.
    -SkipBuild stops after the tests.
#>
[CmdletBinding()]
param([string]$Api = '', [string]$GoogleServerClientId = '', [switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Step($name, [scriptblock]$body) {
    Write-Host "=== $name ==="
    & $body
    if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: $name ($LASTEXITCODE)"; exit 1 }
}

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    Write-Host 'FAIL: flutter is not on PATH. Install the Flutter SDK and the Android toolchain (GD4).'
    exit 1
}

Step 'viewer bundle' { & node scripts/build-mobile-viewer.mjs }
Push-Location (Join-Path $Root 'mobile\android')
try {
    Step 'flutter pub get' { & flutter pub get }
    Step 'flutter analyze' { & flutter analyze }
    Step 'flutter test' { & flutter test }
    if (-not $SkipBuild) {
        $defines = @()
        if ($Api) { $defines += "--dart-define=TRUEBEX_API=$Api" }
        if ($GoogleServerClientId) { $defines += "--dart-define=GOOGLE_SERVER_CLIENT_ID=$GoogleServerClientId" }
        Step 'flutter build apk --debug' { & flutter build apk --debug @defines }
        $apk = Join-Path (Get-Location) 'build\app\outputs\flutter-apk\app-debug.apk'
        Write-Host ("APK: {0} ({1:N1} MB)" -f $apk, ((Get-Item $apk).Length / 1MB))
    }
} finally { Pop-Location }
Write-Host 'mobile GREEN'
exit 0
