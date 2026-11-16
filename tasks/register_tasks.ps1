<#
    register_tasks.ps1 - registers this repo's Windows scheduled tasks for the current user.

    Each tasks/*.xml is a Task Scheduler definition with {{REPO}} where the repo root goes,
    and no user identity (the repo is public). The task runs as whoever registers it,
    only while that user is logged on.

        powershell -NoProfile -ExecutionPolicy Bypass -File tasks\register_tasks.ps1
        powershell -NoProfile -ExecutionPolicy Bypass -File tasks\register_tasks.ps1 -DryRun

    -DryRun prints the rendered XML and registers nothing.

    Run it on ONE machine only: the morning refresh pushes master, and two machines doing so
    race each other. Disable the task on the old machine first:
        schtasks /change /tn "Kinneret daily refresh" /disable

    The old "DailyAgent-Kinneret" task is retired (it ran the agent without committing);
    do not register it again.
#>
param([switch]$DryRun)

$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot

foreach ($file in Get-ChildItem -Path $PSScriptRoot -Filter '*.xml') {
    $xml = (Get-Content -Raw -Encoding utf8 -Path $file.FullName).Replace('{{REPO}}', $Repo)
    $name = ([xml]$xml).Task.RegistrationInfo.URI.TrimStart('\')

    if ($DryRun) {
        Write-Output $xml
        continue
    }
    Register-ScheduledTask -TaskName $name -Xml $xml -User $env:USERNAME -Force | Out-Null
    Write-Host "Registered '$name' for $env:USERNAME, running from $Repo"
}
