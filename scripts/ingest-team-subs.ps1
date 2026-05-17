# ingest-team-subs.ps1
#
# Re-runnable team-subreddit ingest. Run after the playoff bracket changes
# or whenever you want to broaden coverage. Idempotent: existing articles
# UPSERT, so it's safe to re-run.
#
# Usage:
#   pwsh -File scripts\ingest-team-subs.ps1
#   pwsh -File scripts\ingest-team-subs.ps1 -LimitPerSub 25
#
# Default config matches Phase L.3 (12 team subs, 15 threads each, 8
# top-level comments) which produced ~190 chunks for ~$0.01 in Voyage
# embeddings.

[CmdletBinding()]
param(
    [int]$LimitPerSub = 15,
    [int]$TopComments = 8,
    [string]$Listing = "top",
    [string]$Timeframe = "month"
)

$ProjectRoot = "C:\nbarag"
$UV = "C:\Users\isaia\.local\bin\uv.exe"

# Team subreddits NOT already in the corpus from Phase B.8. Add/remove as
# the playoff bracket evolves.
$Subs = @(
    "lakers", "warriors", "bostonceltics", "heat",
    "denvernuggets", "timberwolves",
    "sixers", "Mavericks", "MkeBucks", "pacers",
    "orlandomagic", "suns"
)

Write-Host "Ingesting from $($Subs.Count) subs: $($Subs -join ', ')" -ForegroundColor Cyan

$subArgs = @()
foreach ($s in $Subs) { $subArgs += @("--sub", $s) }

$args = @(
    "run", "--no-sync",
    "python", "-m", "src.ingest_prose.cli", "reddit"
) + $subArgs + @(
    "--listing", $Listing,
    "--timeframe", $Timeframe,
    "--limit-per-sub", $LimitPerSub,
    "--top-comments", $TopComments
)

Push-Location $ProjectRoot
try {
    & $UV @args
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Ingest failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
    Write-Host "Ingest complete. Run 'python -m src.ingest_prose.cli status' for counts." -ForegroundColor Green
} finally {
    Pop-Location
}
