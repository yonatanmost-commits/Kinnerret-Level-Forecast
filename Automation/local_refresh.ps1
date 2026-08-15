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
    # Write-Host, not Write-Output: this function is called from inside other
    # functions, and anything on the output stream would be captured as part of
    # their return value. The file log is the durable record; the console copy
    # is only for running this by hand.
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

<#
    Windows PowerShell 5.1 wraps every stderr line from a native executable in
    an ErrorRecord, and git writes ordinary progress ("From https://...") to
    stderr. Under $ErrorActionPreference = 'Stop' that turns healthy output
    into a terminating error, so native calls are run with the preference
    relaxed and judged by their exit code instead - which is the only reliable
    signal anyway.
#>
function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$Quiet
    )
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & $Exe @Arguments 2>&1
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    if (-not $Quiet) {
        foreach ($line in $output) {
            $text = if ($null -eq $line) { '' } else { $line.ToString() }
            if ($text.Trim()) { Write-Log "  $text" }
        }
    }
    return $code
}

Set-Location $RepoRoot
Write-Log "=== local refresh starting in $RepoRoot ==="

# A dirty tree means hand-edits are in progress; committing them from a
# scheduled task would sweep up work the user did not mean to publish.
$dirty = & git status --porcelain -- "Gold Data" "Silver Data" "Models"
if ($dirty) {
    Write-Log 'ABORT: uncommitted changes under Gold Data/, Silver Data/ or Models/.'
    foreach ($d in $dirty) { Write-Log "  $d" }
    Write-Log 'Commit or discard them, then re-run.'
    exit 1
}

Write-Log 'Rebasing onto origin/master ...'
$code = Invoke-Native git @('pull', '--rebase', '--autostash', 'origin', 'master')
if ($code -ne 0) { Write-Log "ABORT: pull failed (exit $code)."; exit 1 }

Write-Log 'Running the daily agent ...'
$env:PYTHONIOENCODING = 'utf-8'
$danExit = Invoke-Native python @('-X', 'utf8', 'Automation/daily_agent.py')
Write-Log "Daily agent exit code: $danExit"

# Commit whatever the agent produced even if one of its steps failed - a good
# level update should not be thrown away because an unrelated fetch broke.
Invoke-Native git @('add', '--', 'Gold Data', 'Silver Data', 'Models') -Quiet | Out-Null

$pending = & git diff --cached --name-only
if (-not $pending) {
    Write-Log 'No data changed - nothing to push.'
} else {
    foreach ($p in $pending) { Write-Log "  staged: $p" }
    $stamp = Get-Date -Format 'yyyy-MM-dd'
    $message = @"
data: local refresh $stamp

Run of Automation/daily_agent.py from a residential IP, which supplies the
lake level series that CI cannot fetch.
"@
    $code = Invoke-Native git @('commit', '-m', $message)
    if ($code -ne 0) { Write-Log "ABORT: commit failed (exit $code)."; exit 1 }

    Write-Log 'Pushing to origin/master ...'
    $code = Invoke-Native git @('push', 'origin', 'master')
    if ($code -ne 0) { Write-Log "ABORT: push failed (exit $code)."; exit 1 }
    Write-Log 'Pushed. Streamlit Community Cloud will redeploy.'
}

if ($danExit -ne 0) {
    Write-Log 'Finished, but the agent reported a failed step - see above.'
    exit 1
}

Write-Log '=== local refresh finished cleanly ==='
exit 0
