#Requires -Version 7
# setup.ps1 — One-time setup for code-agent on Windows (native, no WSL2 required).
# Run from the code-agent\ project root:
#   pwsh -ExecutionPolicy Bypass -File scripts\setup.ps1

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$ConfigPath = Join-Path $ProjectDir "config\config.yaml"

function Write-Info  { param($Msg) Write-Host "[INFO]  $Msg" -ForegroundColor Green }
function Write-Warn  { param($Msg) Write-Host "[WARN]  $Msg" -ForegroundColor Yellow }
function Write-Err   { param($Msg) Write-Host "[ERROR] $Msg" -ForegroundColor Red }

# ---- Step 1: Validate config file --------------------------------------------
Write-Info "Reading configuration from $ConfigPath ..."
if (-not (Test-Path $ConfigPath)) {
    Write-Err "config\config.yaml not found. Run from the code-agent\ project root."
    exit 1
}

# ---- Step 2: Read OUTPUT_BASE from config.yaml -------------------------------
$OutputBase = & python -c @"
import yaml, pathlib
raw = yaml.safe_load(open(r'$ConfigPath'))
base = raw.get('output', {}).get('base_dir', '~/agent-output')
print(pathlib.Path(base).expanduser())
"@ 2>$null
if (-not $OutputBase) {
    $OutputBase = Join-Path $env:USERPROFILE "agent-output"
}
Write-Info "Output base directory: $OutputBase"

# ---- Step 3: Proxy notice ----------------------------------------------------
Write-Info "Checking proxy environment..."
if ($env:HTTP_PROXY -or $env:HTTPS_PROXY) {
    Write-Info "Proxy detected:"
    if ($env:HTTP_PROXY)  { Write-Info "  HTTP_PROXY  = $env:HTTP_PROXY" }
    if ($env:HTTPS_PROXY) { Write-Info "  HTTPS_PROXY = $env:HTTPS_PROXY" }
    Write-Warn "Verify these are correct for pip install and ollama pull."
} else {
    Write-Info "No proxy variables set."
}

# ---- Step 4: Tool checks -----------------------------------------------------
Write-Info "Checking required tools..."
$Missing = @()
foreach ($cmd in @("java", "mvn", "python", "git")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        $Missing += $cmd
    }
}
if ($Missing.Count -gt 0) {
    Write-Err "Missing required tools: $($Missing -join ', ')"
    Write-Err "Download links:"
    Write-Err "  java/jdk : https://adoptium.net"
    Write-Err "  maven    : https://maven.apache.org/download.cgi"
    Write-Err "  python   : https://www.python.org/downloads/"
    Write-Err "  git      : https://git-scm.com/download/win"
    Write-Err "After installing, restart PowerShell and re-run this script."
    exit 1
}
Write-Info "  java   : $((java -version 2>&1)[0])"
Write-Info "  maven  : $((mvn --version 2>&1)[0])"
Write-Info "  python : $(python --version 2>&1)"

# ---- Step 5: GPU detection and model selection -------------------------------
Write-Info "Detecting GPU..."
$SelectedModel = "codellama:7b-q4"
$GpuVramGb     = 0

try {
    $NvOut = & nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null
    if ($LASTEXITCODE -eq 0 -and $NvOut) {
        $VramMb    = [int]($NvOut.ToString().Trim().Split("`n")[0].Trim())
        $GpuVramGb = [int]($VramMb / 1024)
        Write-Info "NVIDIA GPU detected: $GpuVramGb GB VRAM"
        if     ($GpuVramGb -ge 24) { $SelectedModel = "qwen2.5-coder:32b" }
        elseif ($GpuVramGb -ge 8)  { $SelectedModel = "codellama:13b-q4"  }
        else {
            $SelectedModel = "codellama:7b-q4"
            Write-Warn "GPU has less than 8 GB VRAM — using CPU-friendly 7B model."
        }
    }
} catch {
    Write-Warn "GPU detection failed: $_"
}

if ($GpuVramGb -eq 0) {
    Write-Warn "No NVIDIA GPU detected — using CPU-optimized model (codellama:7b-q4)."
    Write-Warn "The agent will still work; each LLM call will be slower on CPU."
}
Write-Info "Selected model: $SelectedModel  (GPU VRAM: $GpuVramGb GB)"

# ---- Step 6: Ollama check ----------------------------------------------------
Write-Info "Checking Ollama at http://localhost:11434 ..."
try {
    $null = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5
    Write-Info "Ollama is reachable."
} catch {
    Write-Warn "Ollama is not reachable at http://localhost:11434"
    Write-Warn "Install from https://ollama.com and start the Ollama app."
    Write-Warn "Continuing setup — test Ollama connectivity later."
}

# ---- Step 7: Pull LLM and embedding models -----------------------------------
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Info "Pulling LLM model: $SelectedModel ..."
    & ollama pull $SelectedModel
    if ($LASTEXITCODE -ne 0) { Write-Warn "Model pull failed — check Ollama is running." }

    Write-Info "Pulling embedding model: nomic-embed-text ..."
    & ollama pull nomic-embed-text
    if ($LASTEXITCODE -ne 0) { Write-Warn "Embedding model pull failed." }
} else {
    Write-Warn "ollama not in PATH — skipping model pull."
    Write-Warn "Pull manually after installing Ollama:"
    Write-Warn "  ollama pull $SelectedModel"
    Write-Warn "  ollama pull nomic-embed-text"
}

# ---- Step 8: Update config.yaml with selected model --------------------------
Write-Info "Writing selected model to config.yaml ..."
& python -c @"
import re
config_path = r'$ConfigPath'
with open(config_path, encoding='utf-8') as f:
    content = f.read()
content = re.sub(
    r'(^\s{2}model:\s*)["\']?[^"\'\\n#]+["\']?',
    r'\g<1>\"$SelectedModel\"',
    content,
    flags=re.MULTILINE,
)
with open(config_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('config.yaml updated: model = $SelectedModel')
"@

# ---- Step 9: Python virtualenv -----------------------------------------------
Write-Info "Creating Python virtual environment at $ProjectDir\venv ..."
Push-Location $ProjectDir
& python -m venv venv
& "venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
& "venv\Scripts\pip.exe" install -r requirements.txt
Pop-Location
Write-Info "Python dependencies installed."

# ---- Step 10: Create output directories --------------------------------------
Write-Info "Creating output directories under $OutputBase ..."
$SubDirs = @(
    "chromadb",
    "reports",
    "generated-tests\java",
    "generated-tests\python",
    "semgrep-rules",
    "nvd-data",
    "dc-report"
)
foreach ($d in $SubDirs) {
    New-Item -ItemType Directory -Force -Path (Join-Path $OutputBase $d) | Out-Null
}
Write-Info "Output directories created."

# ---- Step 11: Semgrep check --------------------------------------------------
if (Get-Command semgrep -ErrorAction SilentlyContinue) {
    Write-Info "semgrep found: $(semgrep --version 2>&1)"
} else {
    Write-Warn "semgrep not found. Install with: pip install semgrep"
}

# ---- Step 12: Task Scheduler hint --------------------------------------------
$CronExpr = & python -c @"
import yaml
raw = yaml.safe_load(open(r'$ConfigPath'))
print(raw.get('schedule', {}).get('cron_expression', '0 2 * * 0'))
"@ 2>$null

Write-Host ""
Write-Warn "============================================================="
Write-Warn "OPTIONAL: Schedule weekly run with Windows Task Scheduler"
Write-Warn "============================================================="
Write-Warn "Cron expression in config.yaml: $CronExpr  (Sunday 02:00 AM)"
Write-Warn ""
Write-Warn "Run this in an elevated PowerShell to register the task:"
Write-Warn ""
Write-Warn '  $Action  = New-ScheduledTaskAction -Execute "pwsh" -Argument "-File \"' + "$ProjectDir\scripts\run_agent.ps1" + '\""'
Write-Warn '  $Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 2am'
Write-Warn '  $Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable'
Write-Warn '  Register-ScheduledTask -TaskName "CodeAgent" -Action $Action -Trigger $Trigger -Settings $Settings -RunLevel Highest'
Write-Warn "============================================================="

# ---- Final summary -----------------------------------------------------------
Write-Host ""
Write-Info "============================================================="
Write-Info "SETUP COMPLETE"
Write-Info "============================================================="
Write-Host ""
Write-Host "  Platform : Windows (native)"
Write-Host "  Model    : $SelectedModel"
Write-Host "  Output   : $OutputBase"
Write-Host ""
Write-Host "  REQUIRED: Edit config\config.yaml and set:"
Write-Host "    repos.java_repo_path   <- path to your Spring Boot project"
Write-Host "    repos.python_repo_path <- path to your FastAPI project"
Write-Host ""
Write-Host "  OPTIONAL: Override via environment variables (no file edit):"
Write-Host "    `$env:AGENT_OLLAMA_HOST = 'localhost'"
Write-Host "    `$env:AGENT_OUTPUT_BASE = 'D:\my-output'"
Write-Host "    `$env:AGENT_LLM_MODEL   = 'codellama:13b-q4'"
Write-Host ""
Write-Host "  Verify setup with a dry-run:"
Write-Host "    venv\Scripts\activate.ps1"
Write-Host "    python agent\main.py --dry-run"
Write-Host ""
