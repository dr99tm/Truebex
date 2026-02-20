# Build script that outputs to custom directory
$targetDir = "X:\Truebex_site_files\Truebex"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Building site..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
npm run build

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed! Exiting..." -ForegroundColor Red
    exit 1
}

# Check if out folder exists
if (-not (Test-Path out)) {
    Write-Host "ERROR: Build completed but out folder not found!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Copying files to target directory..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Target: $targetDir" -ForegroundColor Yellow

# Create target directory if it doesn't exist
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    Write-Host "Created target directory" -ForegroundColor Gray
}

# Copy all files from out to target directory
Copy-Item -Path "out\*" -Destination $targetDir -Recurse -Force

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Build complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Built files are in: $targetDir" -ForegroundColor Yellow
Write-Host ""
