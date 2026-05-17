# sync-to-onedrive.ps1
#
# One-way mirror from C:\nbarag (source of truth) to the OneDrive backup copy.
# Run after a session if you want the OneDrive folder to stay in sync.
#
# This is a /MIR mirror: files removed at C:\nbarag will also be removed
# from OneDrive. Do NOT edit files in OneDrive; they will be overwritten.
#
# Usage:
#   pwsh -File scripts\sync-to-onedrive.ps1
#   pwsh -File scripts\sync-to-onedrive.ps1 -DryRun
#
# Heavy regenerable folders are excluded so OneDrive does not have to sync
# 450+ MB of .venv and node_modules:
#   .venv, node_modules, .next, dist, __pycache__, .pytest_cache,
#   .mypy_cache, .ruff_cache, .pyright

[CmdletBinding()]
param(
    [switch]$DryRun
)

$Source = "C:\nbarag"
$Dest   = "C:\Users\isaia\OneDrive\Documents\2025 Docs\Claude Copy\RAG Pipelines\NBA Scouting & Stats RAG System"

if (-not (Test-Path $Source)) {
    Write-Error "Source not found: $Source"
    exit 1
}
if (-not (Test-Path $Dest)) {
    Write-Error "Destination not found: $Dest"
    exit 1
}

$excludeDirs = @(
    ".venv", "node_modules", ".next", "dist",
    "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".pyright"
)
$excludeFiles = @(".DS_Store", "Thumbs.db", "desktop.ini")

$args = @(
    $Source, $Dest,
    "/MIR",          # mirror (additions + deletions)
    "/R:1", "/W:1",  # 1 retry, 1 sec wait
    "/NFL", "/NDL", "/NP",  # less verbose output
    "/XD"
) + $excludeDirs + @("/XF") + $excludeFiles

if ($DryRun) {
    $args += "/L"   # list only, no changes
    Write-Host "DRY RUN — no files will be changed" -ForegroundColor Yellow
}

Write-Host "Syncing $Source -> $Dest" -ForegroundColor Cyan
$start = Get-Date
& robocopy.exe @args
$rc = $LASTEXITCODE
$elapsed = (Get-Date) - $start

# robocopy exit codes: 0-7 = OK (various success states), 8+ = error
if ($rc -ge 8) {
    Write-Error "Sync failed (exit $rc) after $($elapsed.TotalSeconds)s"
    exit $rc
}
Write-Host "Sync OK (exit $rc) in $([math]::Round($elapsed.TotalSeconds, 1))s" -ForegroundColor Green
exit 0
