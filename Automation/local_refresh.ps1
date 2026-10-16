<#
    local_refresh.ps1 - the local half of the hybrid refresh.

    GitHub Actions runs the daily agent already, but kineret.org.il sits behind
    Cloudflare and challenges the runner's datacenter IP, so the lake level is
    the one series CI cannot fetch. This script runs the same agent from a
    machine with a residential IP and pushes the result, which also triggers a
    Streamlit Community Cloud redeploy.

    It is safe to run at any time, including while CI is running: it rebases
    onto whatever the bot has already pushed before committing.

    Conflicts during that rebase: Gold Data/ and Models/ are derived - the agent
    rebuilds them on every run - so a conflict there takes CI's copy and the
    rebase goes on. A conflict anywhere else aborts the rebase, leaving the tree
    and HEAD exactly as they were, and exits 1. (On 2026-10-16 a gold conflict
    left the rebase stopped half-way and the working tree stripped.)

    Register it to run daily (see docs/DEPLOYMENT.md):

        schtasks /create /tn "Kinneret daily refresh" /sc daily /st 07:30 ^
          /tr "powershell -NoProfile -ExecutionPolicy Bypass -File \"<repo>\Automation\local_refresh.ps1\""

    -SyncOnly runs just the rebase step and stops (no agent, no commit, no push).

    Exit codes: 0 = refreshed or already current, 1 = something needs a look.
#>
param([switch]$SyncOnly)

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

$Derived = @('Gold Data/', 'Models/')        # rebuilt by the agent; CI's copy wins a conflict

function Test-MidRebase {
    foreach ($d in 'rebase-merge', 'rebase-apply') {
        if (Test-Path (& git rev-parse --git-path $d)) { return $true }
    }
    return $false
}

<#
    Rebase onto origin/master. Returns $true when the tree is on top of origin,
    $false after aborting (tree and HEAD as before). In a rebase "ours" is the
    side being rebased onto - origin plus the commits already replayed - so
    `checkout --ours` takes CI's copy of a derived file.
#>
function Sync-WithOrigin {
    $code = Invoke-Native git @('pull', '--rebase', '--autostash', 'origin', 'master')
    if ($code -eq 0) { return $true }
    if (-not (Test-MidRebase)) { Write-Log "pull failed before rebasing (exit $code)."; return $false }
    $env:GIT_EDITOR = 'true'                   # keep each commit's message, never open an editor
    while (Test-MidRebase) {
        $conflicts = @(& git diff --name-only --diff-filter=U)
        if ($conflicts.Count -eq 0) {
            Write-Log 'Rebase stopped without a file conflict.'
            break
        }
        $other = @($conflicts | Where-Object { $f = $_; -not ($Derived | Where-Object { $f.StartsWith($_) }) })
        if ($other.Count -gt 0) {
            Write-Log 'Conflict outside the derived data - not resolving it automatically:'
            foreach ($f in $other) { Write-Log "  $f" }
            break
        }
        foreach ($f in $conflicts) { Write-Log "  derived-data conflict, taking CI's copy: $f" }
        Invoke-Native git (@('checkout', '--ours', '--') + $conflicts) -Quiet | Out-Null
        Invoke-Native git (@('add', '--') + $conflicts) -Quiet | Out-Null
        & git diff --cached --quiet
        $step = if ($LASTEXITCODE -eq 0) { 'skip' } else { 'continue' }   # nothing left of this commit
        Invoke-Native git @('rebase', "--$step") | Out-Null
    }
    if (Test-MidRebase) {
        Invoke-Native git @('rebase', '--abort') | Out-Null
        Write-Log 'Rebase aborted; the tree is as it was before the refresh.'
        return $false
    }
    return $true
}

Write-Log 'Rebasing onto origin/master ...'
if (-not (Sync-WithOrigin)) { Write-Log 'ABORT: could not rebase onto origin/master.'; exit 1 }
if ($SyncOnly) { Write-Log 'Synced (-SyncOnly): stopping before the agent.'; exit 0 }

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
