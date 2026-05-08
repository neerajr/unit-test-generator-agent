#!/usr/bin/env bash
# setup.sh — One-time setup for code-agent.
# Supports: Linux (native), WSL2 (Windows), macOS
# Run from the code-agent/ project root: bash scripts/setup.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ---- Step 1: Platform detection -----------------------------------------------
info "Detecting platform..."
PLATFORM="linux"
if [[ "$(uname -s)" == "Darwin" ]]; then
    PLATFORM="macos"
    info "Platform: macOS"
elif grep -qi microsoft /proc/version 2>/dev/null; then
    PLATFORM="wsl2"
    info "Platform: WSL2 (Windows Subsystem for Linux 2)"
elif [[ "$(uname -s)" == "Linux" ]]; then
    PLATFORM="linux"
    info "Platform: Native Linux"
else
    warn "Unknown platform (uname -s = $(uname -s)) — using Linux defaults."
fi

# ---- Step 2: Read OUTPUT_BASE from config.yaml --------------------------------
info "Reading output directory from config/config.yaml..."
OUTPUT_BASE=$(python3 -c "
import yaml, pathlib, sys
try:
    raw = yaml.safe_load(open('$PROJECT_DIR/config/config.yaml'))
    base = raw.get('output', {}).get('base_dir', '~/agent-output')
    print(pathlib.Path(base).expanduser())
except Exception as e:
    sys.stderr.write(str(e) + '\n')
    print(pathlib.Path('~/agent-output').expanduser())
" 2>/dev/null || echo "$HOME/agent-output")
info "Output base: $OUTPUT_BASE"

# ---- Step 3: Proxy notice -----------------------------------------------------
info "Checking proxy environment..."
if [[ -n "${http_proxy:-}" ]] || [[ -n "${https_proxy:-}" ]]; then
    info "Proxy detected:"
    [[ -n "${http_proxy:-}" ]]  && info "  http_proxy  = ${http_proxy}"
    [[ -n "${https_proxy:-}" ]] && info "  https_proxy = ${https_proxy}"
    warn "Verify these are correct for pip install and ollama pull."
else
    info "No proxy variables set. If pip/ollama pull fail, set HTTP_PROXY/HTTPS_PROXY."
fi

# ---- Step 4: Dependency checks ------------------------------------------------
info "Checking required tools..."
MISSING=()
for cmd in java mvn python3 git; do
    command -v "$cmd" &>/dev/null || MISSING+=("$cmd")
done
if [[ ${#MISSING[@]} -gt 0 ]]; then
    error "Missing required tools: ${MISSING[*]}"
    if [[ "$PLATFORM" == "macos" ]]; then
        error "Install with: brew install openjdk maven python git"
        error "Then: brew link openjdk --force"
    elif [[ "$PLATFORM" == "wsl2" || "$PLATFORM" == "linux" ]]; then
        error "Install with: sudo apt update && sudo apt install openjdk-17-jdk maven python3 python3-pip git"
    fi
    exit 1
fi
info "  java   : $(java -version 2>&1 | head -1)"
info "  maven  : $(mvn --version 2>&1 | head -1)"
info "  python : $(python3 --version 2>&1)"

# ---- Step 5: Ollama check and host detection ----------------------------------
info "Checking Ollama..."
OLLAMA_HOST="localhost"

if [[ "$PLATFORM" == "wsl2" ]]; then
    # Ollama typically runs on the Windows host, not inside WSL2
    DETECTED_IP=$(ip route show default 2>/dev/null | awk '/default via/{print $3}' | head -1 || true)
    if [[ -n "$DETECTED_IP" ]] && [[ "$DETECTED_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        OLLAMA_HOST="$DETECTED_IP"
        info "WSL2 Windows host IP auto-detected: $OLLAMA_HOST"
        info "This is set to 'auto' in config.yaml — re-detected every run (IP can change on reboot)."
    else
        warn "Could not detect Windows host IP. Set AGENT_OLLAMA_HOST=<ip> or update environment.ollama_host in config.yaml."
    fi
elif [[ "$PLATFORM" == "macos" ]]; then
    if ! command -v ollama &>/dev/null; then
        warn "Ollama not found. Install from https://ollama.com or: brew install ollama"
        warn "Start with: ollama serve   (or open the Ollama app)"
        warn "Continuing — you can test Ollama connectivity later."
    else
        info "Ollama found: $(command -v ollama)"
    fi
elif [[ "$PLATFORM" == "linux" ]]; then
    if ! command -v ollama &>/dev/null; then
        warn "Ollama not found. Install from https://ollama.com"
        warn "Quick install: curl -fsSL https://ollama.com/install.sh | sh"
        warn "Continuing — you can test Ollama connectivity later."
    else
        info "Ollama found: $(command -v ollama)"
    fi
fi

OLLAMA_PORT=$(python3 -c "
import yaml
raw = yaml.safe_load(open('$PROJECT_DIR/config/config.yaml'))
print(raw.get('environment', {}).get('ollama_port', 11434))
" 2>/dev/null || echo "11434")
OLLAMA_URL="http://${OLLAMA_HOST}:${OLLAMA_PORT}"
info "Ollama URL for connectivity test: $OLLAMA_URL"

# ---- Step 6: GPU detection and model selection --------------------------------
info "Detecting GPU..."
SELECTED_MODEL="codellama:7b-q4"   # safe CPU default
GPU_VRAM_GB=0

if command -v nvidia-smi &>/dev/null; then
    VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null \
              | head -1 | tr -d ' \r' || true)
    if [[ -n "$VRAM_MB" ]] && [[ "$VRAM_MB" =~ ^[0-9]+$ ]]; then
        GPU_VRAM_GB=$(( VRAM_MB / 1024 ))
        info "NVIDIA GPU detected: ${GPU_VRAM_GB} GB VRAM"
        if   (( GPU_VRAM_GB >= 24 )); then SELECTED_MODEL="qwen2.5-coder:32b"
        elif (( GPU_VRAM_GB >= 8  )); then SELECTED_MODEL="codellama:13b-q4"
        else
            SELECTED_MODEL="codellama:7b-q4"
            warn "GPU has less than 8 GB VRAM — using CPU-friendly 7B model."
        fi
    else
        warn "nvidia-smi found but VRAM query returned no result — assuming CPU mode."
    fi
elif [[ "$PLATFORM" == "macos" ]] && system_profiler SPDisplaysDataType 2>/dev/null | grep -q "Metal"; then
    info "macOS with Metal GPU detected. Ollama uses Metal automatically."
    SELECTED_MODEL="codellama:13b-q4"
    warn "Using codellama:13b-q4. Upgrade to qwen2.5-coder:32b if you have M1 Pro/Max/Ultra or M2+."
else
    warn "No NVIDIA GPU detected — using CPU-optimized model (codellama:7b-q4)."
    warn "The agent will still work, but each LLM call will be slower on CPU."
fi
info "Selected model: $SELECTED_MODEL  (GPU VRAM: ${GPU_VRAM_GB} GB)"

# Write selected model back to config.yaml (preserving comments)
python3 - <<PYEOF
import re
config_path = '$PROJECT_DIR/config/config.yaml'
with open(config_path, encoding='utf-8') as f:
    content = f.read()
content = re.sub(
    r'(^  model:\s*)["\']?[^"\'\\n#]+["\']?',
    r'\g<1>"$SELECTED_MODEL"',
    content,
    flags=re.MULTILINE,
)
with open(config_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated config.yaml: model = $SELECTED_MODEL')
PYEOF

# ---- Step 7: Pull LLM and embedding models ------------------------------------
info "Pulling LLM model: $SELECTED_MODEL ..."
if command -v ollama &>/dev/null; then
    ollama pull "$SELECTED_MODEL" \
        || warn "Model pull failed — ensure Ollama is running at $OLLAMA_URL and retry."
    info "Pulling embedding model: nomic-embed-text..."
    ollama pull nomic-embed-text \
        || warn "Embedding model pull failed — check Ollama connectivity."
else
    warn "ollama not in PATH — skipping model pull. Pull manually after Ollama is installed:"
    warn "  ollama pull $SELECTED_MODEL"
    warn "  ollama pull nomic-embed-text"
fi

# ---- Step 8: Python virtualenv ------------------------------------------------
info "Creating Python virtual environment at $PROJECT_DIR/venv..."
cd "$PROJECT_DIR"
python3 -m venv venv
# shellcheck source=/dev/null
source venv/bin/activate
info "Installing Python dependencies from requirements.txt..."
pip3 install --upgrade pip --quiet
pip3 install -r requirements.txt
info "Python dependencies installed."

# ---- Step 9: Create output directories ----------------------------------------
info "Creating output directories under $OUTPUT_BASE..."
mkdir -p \
    "$OUTPUT_BASE/chromadb" \
    "$OUTPUT_BASE/reports" \
    "$OUTPUT_BASE/generated-tests/java" \
    "$OUTPUT_BASE/generated-tests/python" \
    "$OUTPUT_BASE/semgrep-rules" \
    "$OUTPUT_BASE/nvd-data" \
    "$OUTPUT_BASE/dc-report"
info "Output directories created."

# ---- Step 10: Semgrep rules (one-time download) -------------------------------
info "Attempting to download Semgrep OWASP Top Ten rules..."
if command -v semgrep &>/dev/null; then
    SEMGREP_CACHE="$HOME/.semgrep/cache"
    mkdir -p "$SEMGREP_CACHE"
    if semgrep --config p/owasp-top-ten --dry-run /dev/null --json >/dev/null 2>&1; then
        if [[ -d "$SEMGREP_CACHE" ]]; then
            cp -r "$SEMGREP_CACHE"/. "$OUTPUT_BASE/semgrep-rules/" 2>/dev/null || true
            info "Semgrep rules cached to $OUTPUT_BASE/semgrep-rules/"
        fi
    else
        warn "Semgrep rules download failed. Download manually from:"
        warn "  https://github.com/returntocorp/semgrep-rules"
        warn "  Then copy YAML files to: $OUTPUT_BASE/semgrep-rules/"
    fi
else
    warn "semgrep not found — skipping rules download."
    if [[ "$PLATFORM" == "macos" ]]; then
        warn "Install with: brew install semgrep"
    else
        warn "Install with: pip3 install semgrep"
    fi
fi

# ---- Step 11: Cron / scheduler registration -----------------------------------
CRON_EXPR=$(python3 -c "
import yaml
raw = yaml.safe_load(open('$PROJECT_DIR/config/config.yaml'))
print(raw.get('schedule', {}).get('cron_expression', '0 2 * * 0'))
" 2>/dev/null || echo "0 2 * * 0")
LOG_FILE="$OUTPUT_BASE/reports/run.log"

if [[ "$PLATFORM" == "wsl2" || "$PLATFORM" == "linux" ]]; then
    info "Registering cron job: $CRON_EXPR ..."
    CRON_CMD="$CRON_EXPR $PROJECT_DIR/scripts/run_agent.sh >> $LOG_FILE 2>&1"
    if crontab -l 2>/dev/null | grep -qF "run_agent.sh"; then
        warn "Cron entry already exists — skipping."
    else
        (crontab -l 2>/dev/null || true; echo "$CRON_CMD") | crontab -
        info "Cron job registered."
    fi

    if [[ "$PLATFORM" == "wsl2" ]]; then
        echo ""
        warn "============================================================"
        warn "WSL2: CRON DOES NOT START AUTOMATICALLY ON WINDOWS BOOT"
        warn "============================================================"
        warn "Choose ONE option to auto-start cron:"
        warn ""
        warn "  Option A — /etc/wsl.conf (requires WSL2 >= 0.67.6):"
        warn "    sudo tee -a /etc/wsl.conf <<EOF"
        warn "    [boot]"
        warn "    command=service cron start"
        warn "    EOF"
        warn ""
        warn "  Option B — Windows Task Scheduler:"
        warn "    Program : C:\\Windows\\System32\\wsl.exe"
        warn "    Args    : -e sudo service cron start"
        warn "    Trigger : At startup / At log on"
        warn "============================================================"
    fi

elif [[ "$PLATFORM" == "macos" ]]; then
    warn "============================================================"
    warn "macOS: Schedule the agent via crontab or launchd."
    warn "To use crontab, run: crontab -e  and add:"
    warn "  $CRON_EXPR $PROJECT_DIR/scripts/run_agent.sh >> $LOG_FILE 2>&1"
    warn "============================================================"
fi

# ---- Step 12: Make scripts executable -----------------------------------------
chmod +x "$PROJECT_DIR/scripts/run_agent.sh"
info "run_agent.sh marked executable."

# ---- Final checklist ----------------------------------------------------------
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}SETUP COMPLETE${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "  Platform detected : $PLATFORM"
echo "  Model selected    : $SELECTED_MODEL"
echo "  Output directory  : $OUTPUT_BASE"
echo ""
echo "  REQUIRED: Edit config/config.yaml and set:"
echo "    repos.java_repo_path   <- path to your Spring Boot project"
echo "    repos.python_repo_path <- path to your FastAPI project"
echo ""
echo "  OPTIONAL overrides (no file edit needed — set as env vars):"
echo "    AGENT_OLLAMA_HOST  <- Ollama host if auto-detection is wrong"
echo "    AGENT_OUTPUT_BASE  <- different output root"
echo "    AGENT_LLM_MODEL    <- different model"
echo ""
echo "  Verify setup with a dry-run:"
echo "    source venv/bin/activate"
echo "    python3 agent/main.py --dry-run"
echo ""
echo "  Also add to your Java pom.xml:"
echo "    JaCoCo plugin (for coverage reports)"
echo "    SpotBugs plugin (for static analysis)"
echo "    See README.md for copy-paste snippets."
echo ""
