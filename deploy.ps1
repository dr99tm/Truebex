# Deployment script for GitHub Pages
# This script builds and deploys without manually copying files

Write-Host "Building site..." -ForegroundColor Green
npm run build

Write-Host "Switching to gh-pages branch..." -ForegroundColor Green
git checkout gh-pages

Write-Host "Cleaning old files..." -ForegroundColor Green
# Remove all files except .git and out folder
Get-ChildItem -Exclude .git,out | Remove-Item -Recurse -Force

Write-Host "Moving out folder contents to root..." -ForegroundColor Green
# Move everything from out to root
Get-ChildItem -Path out -Force | Move-Item -Destination . -Force

# Remove empty out folder
Remove-Item out -Force -ErrorAction SilentlyContinue

# Ensure .nojekyll exists
if (-not (Test-Path .nojekyll)) {
    New-Item -ItemType File -Name .nojekyll -Force | Out-Null
}

Write-Host "Staging changes..." -ForegroundColor Green
git add .

Write-Host "Committing..." -ForegroundColor Green
git commit -m "Deploy: Update site $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

Write-Host "Pushing to GitHub..." -ForegroundColor Green
git push origin gh-pages --force

Write-Host "Switching back to master..." -ForegroundColor Green
git checkout master

Write-Host "`nDeployment complete! Site will update in 1-2 minutes." -ForegroundColor Green
