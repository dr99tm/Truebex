<#
.SYNOPSIS
    Copy one contract's fixtures from the app repository into
    server\tests\contracts\<Contract>\ (PF14d; the app side is authoritative, C.9).

.DESCRIPTION
    Copies, never edits. The files are read as COMMITTED on -Ref (default main)
    with `git archive`, so the bytes are the app repository's blobs whatever its
    checkout does to line endings: the app checkout on the owner's PC has
    core.autocrlf=true, so its working tree holds CRLF copies of LF files.
    Nothing in the app repository is written: rev-parse, ls-tree and archive only
    read, and the archive goes to a temporary folder.

    After the copy every file's git blob id is compared with the app's (a
    byte-exact check), files the app no longer has are removed (README.md is
    written here and kept), and the app commit is printed for the folder's
    README and the feature's As-built. `.gitattributes` keeps
    server/tests/contracts/** as -text, so git stores the bytes as they are.

    Then run the contract's tests (server\tests\test_<contract>.py), fix what
    the new fixtures break, update the folder's README.md and commit.

.PARAMETER Contract
    The fixture folder's name under Docs\roadmap\fixtures\contracts\ (telemetry, licence, ...).

.PARAMETER AppRepo
    The app repository (default T:\unreal5_7_4_projects\truebex_compact).

.PARAMETER Ref
    The app branch, tag or commit to copy from (default main).

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\sync-contract-fixtures.ps1 -Contract telemetry
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[a-z0-9-]+$')][string]$Contract,
    [string]$AppRepo = 'T:\unreal5_7_4_projects\truebex_compact',
    [string]$Ref = 'main'
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Src = "Docs/roadmap/fixtures/contracts/$Contract"
$Dest = Join-Path $Root "server\tests\contracts\$Contract"

$commit = & git -C $AppRepo rev-parse --short=8 "$Ref^{commit}"
if ($LASTEXITCODE -ne 0 -or -not $commit) { throw "$AppRepo has no commit $Ref" }

# The app's blobs on the ref: "<mode> blob <id><TAB><path>".
$blobs = @{}
foreach ($line in (& git -C $AppRepo ls-tree -r $Ref -- "$Src/")) {
    if ($line -match '^\d+ blob ([0-9a-f]{40})\t(.+)$') {
        $blobs[$Matches[2].Substring($Src.Length + 1)] = $Matches[1]
    }
}
if ($blobs.Count -eq 0) { throw "$AppRepo has no $Src on $Ref" }

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("truebex-fixtures-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
    $zip = Join-Path $tmp 'fixtures.zip'
    # core.autocrlf=false for this one command: the archive holds the blobs, not CRLF copies.
    & git -C $AppRepo -c core.autocrlf=false archive --format=zip -o $zip $Ref $Src
    if ($LASTEXITCODE -ne 0) { throw "git archive failed in $AppRepo" }
    $out = Join-Path $tmp 'out'
    Expand-Archive -Path $zip -DestinationPath $out
    $from = Join-Path $out ($Src -replace '/', '\')

    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
    $updated = @(); $same = @(); $removed = @()
    foreach ($rel in ($blobs.Keys | Sort-Object)) {
        $target = Join-Path $Dest ($rel -replace '/', '\')
        $before = if (Test-Path $target) { (& git hash-object --no-filters -- $target) } else { '' }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath (Join-Path $from ($rel -replace '/', '\')) -Destination $target -Force
        $after = & git hash-object --no-filters -- $target
        if ($after -ne $blobs[$rel]) { throw "$rel is not byte-exact after the copy ($after, the app has $($blobs[$rel]))" }
        if ($before -eq $after) { $same += $rel } else { $updated += $rel }
    }
    foreach ($file in (Get-ChildItem -Path $Dest -Recurse -File)) {
        $rel = $file.FullName.Substring($Dest.Length + 1) -replace '\\', '/'
        if ($rel -ne 'README.md' -and -not $blobs.ContainsKey($rel)) {
            Remove-Item -LiteralPath $file.FullName -Force
            $removed += $rel
        }
    }
} finally {
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "copied $($blobs.Count) files of $Src from $AppRepo $Ref ($commit), each byte-exact to the app's blob"
Write-Host ("  updated:   " + $(if ($updated) { $updated -join ', ' } else { '-' }))
Write-Host ("  unchanged: " + $(if ($same) { $same -join ', ' } else { '-' }))
Write-Host ("  removed:   " + $(if ($removed) { $removed -join ', ' } else { '-' }))
Write-Host "Next: server\.venv\Scripts\python.exe -m pytest -q server\tests\test_$($Contract -replace '-', '_').py, update $Dest\README.md (app commit $commit), commit."
