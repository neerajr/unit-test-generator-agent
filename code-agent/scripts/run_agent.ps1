#Requires -Version 7
# run_agent.ps1 — Windows Task Scheduler entry point for the weekly agent run.
# Schedule: see schedule.cron_expression in config/config.yaml (default: Sunday 02:00 AM)
#
# To register as a scheduled task (run once in elevated PowerShell):
#   $Action  = New-ScheduledTaskAction -Execute "pwsh" -Argument "-File `"<path>\scripts\run_agent.ps1`""
#   $Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 2am
#   $Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
#   Register-ScheduledTask -TaskName "CodeAgent" -Action $Action -Trigger $Trigger -Settings $Settings -RunLevel Highest

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$ConfigPath = Join-Path $ProjectDir "config\config.yaml"
$VenvPython = Join-Path $ProjectDir "venv\Scripts\python.exe"

# Read OUTPUT_BASE from config.yaml
$OutputBase = & python -c @"
import yaml, pathlib
try:
    raw = yaml.safe_load(open(r'$ConfigPath'))
    base = raw.get('output', {}).get('base_dir', '~/agent-output')
    print(pathlib.Path(base).expanduser())
except Exception:
    import os
    print(os.path.join(os.path.expanduser('~'), 'agent-output'))
"@ 2>$null
if (-not $OutputBase) {
    $OutputBase = Join-Path $env:USERPROFILE "agent-output"
}

$ReportsDir = Join-Path $OutputBase "reports"
$LogFile    = Join-Path $ReportsDir "run.log"
New-Item -ItemType Directory -Force -Path $ReportsDir | Out-Null

# Validate venv exists
if (-not (Test-Path $VenvPython)) {
    $Msg = "[ERROR] Python venv not found at $VenvPython. Run scripts\setup.ps1 first."
    Add-Content -Path $LogFile -Value $Msg
    Write-Error $Msg
    exit 1
}

# Log run start
$StartTime = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
Add-Content -Path $LogFile -Value "======================================="
Add-Content -Path $LogFile -Value "code-agent run started: $StartTime"
Add-Content -Path $LogFile -Value "======================================="

# Run the agent
Push-Location $ProjectDir
try {
    & $VenvPython agent\main.py 2>&1 | Tee-Object -Append -FilePath $LogFile
    $ExitCode = $LASTEXITCODE
} catch {
    Add-Content -Path $LogFile -Value "[ERROR] Agent threw an exception: $_"
    $ExitCode = 1
} finally {
    Pop-Location
}

$EndTime = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
Add-Content -Path $LogFile -Value "code-agent run finished: $EndTime (exit code: $ExitCode)"
exit $ExitCode
