<#
    local_refresh.ps1 - the local half of the hybrid refresh.

    GitHub Actions runs the daily agent already, but kineret.org.il sits behind
    Cloudflare and challenges the runner's datacenter IP, so the lake level is
    the one series CI cannot fetch. This script runs the same agent from a
    machine with a residential IP and pushes the result, which also triggers a
    Streamlit Community Cloud redeploy.

    It is safe to run at any time, including while CI is running: it rebases
    onto whatever the bot has already pushed before committing.

    Register it to run daily (see docs/DEPLOYMENT.md):

        schtasks /create /tn "Kinneret daily refresh" /sc daily /st 07:30 ^
          /tr "powershell -NoProfile -ExecutionPolicy Bypass -File \"<repo>\Automation\local_refresh.ps1\""

    Exit codes: 0 = refreshed or already current, 1 = something needs a look.
#>

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir   = Join-Path $RepoRoot 'Reports'
$LogFile  = Join-Path $LogDir ('local_refresh_{0}.log' -f (Get-Date -Format 'yyyy-MM-dd'))

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

function Write-Log {
    param([string]$Message)
    $line = '{0}  {1}' -f (Get-Date -Format 'HH:mm:ss'), $Message
    Write-Output $line
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

Set-Location $RepoRoot
Write-Log "=== local refresh starting in $RepoRoot ==="

# A dirty tree means hand-edits are in progress; committing them from a
# scheduled task would sweep up work the user did not mean to publish.
$dirty = git status --porcelain -- "Gold Data" "Silver Data" "Models"
if ($dirty) {
    Write-Log 'ABORT: uncommitted changes under Gold Data/, Silver Data/ or Models/.'
    Write-Log 'Commit or discard them, then re-run.'
    exit 1
}

Write-Log 'Rebasing onto origin/master ...'
git pull --rebase --autostash origin master 2>&1 | ForEach-Object { Write-Log "  $_" }
if ($LASTEXITCODE -ne 0) { Write-Log 'ABORT: pull failed.'; exit 1 }

Write-Log 'Running the daily agent ...'
$env:PYTHONIOENCODING = 'utf-8'
python -X utf8 Automation/daily_agent.py 2>&1 | ForEach-Object { Write-Log "  $_" }
$danExit = $LASTEXITCODE
Write-Log "Daily agent exit code: $danExit"

# Commit whatever the agent produced even if one of its steps failed - a good
# level update should not be thrown away because an unrelated fetch broke.
git add -- "Gold Data" "Silver Data" "Models"
git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Log 'No data changed - nothing to push.'
} else {
    $stamp = Get-Date -Format 'yyyy-MM-dd'
    git commit -m "data: local refresh $stamp

Run of Automation/daily_agent.py from a residential IP, which supplies the
lake level series that CI cannot fetch." 2>&1 | ForEach-Object { Write-Log "  $_" }

    Write-Log 'Pushing to origin/master ...'
    git push origin master 2>&1 | ForEach-Object { Write-Log "  $_" }
    if ($LASTEXITCODE -ne 0) { Write-Log 'ABORT: push failed.'; exit 1 }
    Write-Log 'Pushed. Streamlit Community Cloud will redeploy.'
}

if ($danExit -ne 0) {
    Write-Log 'Finished, but the agent reported a failed step - see above.'
    exit 1
}

Write-Log '=== local refresh finished cleanly ==='
exit 0
