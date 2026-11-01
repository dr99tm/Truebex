<#
.SYNOPSIS
  Sets up this repository on a Windows machine and checks it.

.DESCRIPTION
  Reads setup\requirements.psd1 (the tools, files and install steps this repo needs), installs any missing
  tool with winget (or the spec's own install command), runs the project install steps, then prints a check
  of every requirement. The same script is copied into each of the owner's repos; only requirements.psd1
  differs. Safe to re-run: anything already present at the right version is left alone.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File setup\setup.ps1                  # the core component
  powershell -ExecutionPolicy Bypass -File setup\setup.ps1 -With postgres   # core + optional components
  powershell -ExecutionPolicy Bypass -File setup\setup.ps1 -All
  powershell -ExecutionPolicy Bypass -File setup\setup.ps1 -Check           # check only, installs nothing
#>
param(
    [switch]$Check,
    [string[]]$With = @(),
    [switch]$All,
    [switch]$SkipProject,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
$Spec = Import-PowerShellDataFile (Join-Path $PSScriptRoot 'requirements.psd1')

$components = @('core') + ($With | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
if ($All) { $components = @($Spec.Components.Keys) }
foreach ($c in $components) {
    if (-not $Spec.Components.ContainsKey($c)) {
        throw "Unknown component '$c'. Known: $(@($Spec.Components.Keys) -join ', ')"
    }
}
function Test-Selected($item) { $components -contains $(if ($item.Component) { $item.Component } else { 'core' }) }

function Expand-Text([string]$s) {
    $s = [Environment]::ExpandEnvironmentVariables($s)
    $s = $s.Replace('{root}', $Root)
    foreach ($m in [regex]::Matches($s, '\{tool:([\w.-]+)\}')) {
        $t = $script:Found[$m.Groups[1].Value]
        if (-not $t) { throw "Step needs tool '$($m.Groups[1].Value)', which was not found" }
        $s = $s.Replace($m.Value, $t)
    }
    return $s
}

function Update-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = (@($machine, $user) | Where-Object { $_ }) -join ';'
}

# Finds a tool: PATH first, then the spec's known install paths. Returns the first copy whose version fits,
# else the first copy found, as @{ Path; Version }, or $null.
function Find-Tool($tool) {
    # Tools such as java print their version on stderr, which 'Stop' would turn into an exception.
    $ErrorActionPreference = 'Continue'
    $candidates = @()
    if (-not $tool.NoPath) {
        foreach ($cmd in @(Get-Command $tool.Command -All -ErrorAction SilentlyContinue)) {
            if ($cmd.Source) { $candidates += $cmd.Source }
        }
    }
    foreach ($p in @($tool.Paths)) {
        if (-not $p) { continue }
        foreach ($r in @(Resolve-Path (Expand-Text $p) -ErrorAction SilentlyContinue)) { $candidates += $r.Path }
    }
    $first = $null
    foreach ($exe in ($candidates | Select-Object -Unique)) {
        $version = $null
        if ($tool.Pattern) {
            $out = ''
            try {
                $out = & $exe @(($tool.Args -split ' ') | Where-Object { $_ }) 2>&1 | Out-String
            } catch { $out = '' }
            $m = [regex]::Match($out, $tool.Pattern)
            if (-not $m.Success) { continue }
            $version = $m.Groups[1].Value
        }
        $hit = @{ Path = $exe; Version = $version }
        if (Test-Version $version $tool.Min $tool.Below) { return $hit }
        if (-not $first) { $first = $hit }
    }
    return $first
}

function Test-Version([string]$have, [string]$min, [string]$max) {
    if (-not $min -and -not $max) { return $true }
    if (-not $have) { return $false }
    $clean = $have -replace '[^\d.].*$', ''
    if ($clean -notmatch '\.') { $clean += '.0' }
    try { $h = [version]$clean } catch { return $false }
    if ($min -and $h -lt [version]$min) { return $false }
    if ($max -and $h -ge [version]$max) { return $false }
    return $true
}

function Get-Winget {
    $cmd = Get-Command winget -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    # Running as SYSTEM (e.g. through AWS SSM) winget isn't on PATH, but the packaged exe works when called directly.
    $exe = Get-ChildItem "$env:ProgramFiles\WindowsApps\Microsoft.DesktopAppInstaller_*_x64__8wekyb3d8bbwe\winget.exe" `
        -ErrorAction SilentlyContinue | Sort-Object FullName | Select-Object -Last 1
    if ($exe) { return $exe.FullName }
    Write-Host '== winget is missing: installing it (Microsoft.WinGet.Client, Repair-WinGetPackageManager)' -ForegroundColor Cyan
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Force | Out-Null
    Install-Module Microsoft.WinGet.Client -Force -Scope AllUsers -AllowClobber | Out-Null
    Import-Module Microsoft.WinGet.Client
    Repair-WinGetPackageManager -AllUsers -Latest | Out-Null
    $cmd = Get-Command winget -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $exe = Get-ChildItem "$env:ProgramFiles\WindowsApps\Microsoft.DesktopAppInstaller_*_x64__8wekyb3d8bbwe\winget.exe" `
        -ErrorAction SilentlyContinue | Sort-Object FullName | Select-Object -Last 1
    if ($exe) { return $exe.FullName }
    throw 'winget could not be installed; install App Installer from the Microsoft Store and re-run'
}

function Install-Tool($tool) {
    if ($tool.Install) {
        Write-Host "== $($tool.Name): $($tool.Install)" -ForegroundColor Cyan
        & powershell -NoProfile -ExecutionPolicy Bypass -Command (Expand-Text $tool.Install)
        if ($LASTEXITCODE -ne 0) { throw "Installing $($tool.Name) failed (exit $LASTEXITCODE)" }
        return
    }
    if (-not $tool.Winget) { throw "$($tool.Name) has no installer in requirements.psd1; install it by hand" }
    $winget = Get-Winget
    $wingetArgs = @('install', '--id', $tool.Winget, '--exact', '--silent', '--disable-interactivity',
        '--accept-package-agreements', '--accept-source-agreements', '--source', 'winget')
    if ($tool.Version) { $wingetArgs += @('--version', $tool.Version) }
    if ($tool.Scope) { $wingetArgs += @('--scope', $tool.Scope) }
    if ($tool.Override) { $wingetArgs += @('--override', $tool.Override) }
    Write-Host "== $($tool.Name): winget $($wingetArgs -join ' ')" -ForegroundColor Cyan
    & $winget @wingetArgs
    # -1978335189 = already installed, -1978335135 = no newer version: both mean it is there.
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189 -and $LASTEXITCODE -ne -1978335135) {
        throw "winget install $($tool.Winget) failed (exit $LASTEXITCODE)"
    }
}

$script:Found = @{}
$rows = New-Object System.Collections.ArrayList

# 1. Tools
foreach ($tool in $Spec.Tools) {
    if (-not (Test-Selected $tool)) { continue }
    $hit = Find-Tool $tool
    $ok = $hit -and (Test-Version $hit.Version $tool.Min $tool.Below)
    if (-not $ok -and -not $Check) {
        Install-Tool $tool
        Update-SessionPath
        $hit = Find-Tool $tool
        $ok = $hit -and (Test-Version $hit.Version $tool.Min $tool.Below)
    }
    if ($hit) { $script:Found[$tool.Name] = $hit.Path }
    $need = @($(if ($tool.Min) { ">=$($tool.Min)" }), $(if ($tool.Below) { "<$($tool.Below)" })) -join ' '
    [void]$rows.Add([pscustomobject]@{
            Kind = 'tool'; Name = $tool.Name; Component = $(if ($tool.Component) { $tool.Component } else { 'core' })
            Status = $(if ($ok) { 'ok' } elseif ($tool.Optional) { 'warn' } else { 'MISSING' })
            Found = $(if ($hit) { "$($hit.Version) $($hit.Path)".Trim() } else { '' }); Need = $need.Trim(); Note = $tool.Note
        })
}

# 2. Project install steps
if (-not $Check -and -not $SkipProject) {
    foreach ($step in $Spec.Steps) {
        if (-not (Test-Selected $step)) { continue }
        if ($step.Skip -and (Test-Path (Join-Path $Root $step.Skip))) { continue }
        $cmd = Expand-Text $step.Run
        $dir = Join-Path $Root $(if ($step.Dir) { $step.Dir } else { '.' })
        Write-Host "== $($step.Name) (in $dir): $cmd" -ForegroundColor Cyan
        Push-Location $dir
        try {
            & powershell -NoProfile -ExecutionPolicy Bypass -Command $cmd
            if ($LASTEXITCODE -ne 0) { throw "Step '$($step.Name)' failed (exit $LASTEXITCODE)" }
        } finally { Pop-Location }
    }
}

# 3. Files that git doesn't carry
foreach ($f in $Spec.Files) {
    if (-not (Test-Selected $f)) { continue }
    $path = Expand-Text $f.Path
    if (-not [IO.Path]::IsPathRooted($path)) { $path = Join-Path $Root $path }
    $there = Test-Path $path
    if (-not $there -and -not $Check -and $f.Template) {
        $template = Join-Path $Root $f.Template
        if (Test-Path $template) {
            Copy-Item $template $path
            $there = $true
            Write-Host "== created $($f.Path) from $($f.Template): review it" -ForegroundColor Yellow
        }
    }
    [void]$rows.Add([pscustomobject]@{
            Kind = 'file'; Name = $f.Path; Component = $(if ($f.Component) { $f.Component } else { 'core' })
            Status = $(if ($there) { 'ok' } elseif ($f.Required) { 'MISSING' } else { 'warn' })
            Found = $(if ($there) { 'present' } else { 'absent' }); Need = $f.Kind; Note = $f.Note
        })
}

if ($Json) {
    $rows | ConvertTo-Json -Depth 3
} else {
    Write-Host ''
    Write-Host "$($Spec.Name): check of components $($components -join ', ')" -ForegroundColor Cyan
    $rows | Format-Table -AutoSize -Wrap Status, Kind, Name, Component, Found, Need, Note | Out-String -Width 220 | Write-Host
    $known = @($Spec.Components.Keys | Where-Object { $components -notcontains $_ })
    if ($known) { Write-Host "Other components: $($known -join ', ') (add with -With <name>; see setup\README.md)" }
}
$missing = @($rows | Where-Object Status -eq 'MISSING')
if ($missing) {
    Write-Host "$($missing.Count) required item(s) missing." -ForegroundColor Red
    exit 1
}
exit 0
