# run_daily_agent.ps1 - Windows Task Scheduler entry point
# Schedule: Daily at 06:00
# Action: powershell.exe -NonInteractive -File "C:\...\Automation\run_daily_agent.ps1"

$python = (Get-Command python).Source
& $python "$PSScriptRoot\daily_agent.py"
exit $LASTEXITCODE
